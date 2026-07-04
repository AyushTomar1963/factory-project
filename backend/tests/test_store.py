import os
import tempfile
import threading
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, InspectionLog, IqcLot, StoreBinItem, User
from store_service import (
    create_grn_from_bin,
    create_store_bins_from_inspection,
    sync_store_from_inspections,
    _allocate_quantities,
)


@pytest.fixture()
def db_session():
    db_path = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    keeper = User(username="store", hashed_password="x", role="store_keeper")
    session.add(keeper)
    session.commit()

    yield session, engine, db_path
    session.close()
    try:
        os.remove(db_path)
    except OSError:
        pass


def _make_inspection_log(session, status="GREEN", lot_quantity=100, part_suffix=""):
    log = InspectionLog(
        part_name="Test Part",
        part_number=f"PN-TEST{part_suffix}",
        stage="Stage 1",
        supplier="Acme",
        invoice_number="INV-1",
        lot_quantity=lot_quantity,
        checking_frequency=100,
        measured_values={"OD": status, "ID": status},
        status=status,
        worker_remark="",
        ai_category="N/A",
        ai_report="{}",
        logged_by="worker",
    )
    session.add(log)
    session.flush()
    return log


def test_grn_only_from_ok_bin(db_session):
    session, _engine, _path = db_session
    log = _make_inspection_log(session, status="RED", lot_quantity=50)
    create_store_bins_from_inspection(session, log)
    session.commit()

    rejected = (
        session.query(StoreBinItem)
        .filter(StoreBinItem.bin_type == "REJECTED")
        .first()
    )
    assert rejected is not None

    with pytest.raises(ValueError, match="OK-bin"):
        create_grn_from_bin(
            session,
            rejected.id,
            "INV-99",
            date.today(),
            "store",
        )


def test_grn_numbers_are_unique_under_concurrent_inward(db_session):
    session, engine, _path = db_session
    Session = sessionmaker(bind=engine)

    ok_item_ids = []
    for idx in range(5):
        log = _make_inspection_log(session, lot_quantity=10 + idx, part_suffix=str(idx))
        create_store_bins_from_inspection(session, log)
        session.flush()
        ok_bin = (
            session.query(StoreBinItem)
            .join(IqcLot, IqcLot.id == StoreBinItem.iqc_lot_id)
            .filter(IqcLot.inspection_log_id == log.id, StoreBinItem.bin_type == "OK")
            .first()
        )
        ok_item_ids.append(ok_bin.id)
    session.commit()

    grn_numbers = []
    errors = []
    lock = threading.Lock()

    def inward(item_id):
        local = Session()
        try:
            grn = create_grn_from_bin(
                local,
                item_id,
                f"INV-{item_id}",
                date.today(),
                "store",
            )
            local.commit()
            with lock:
                grn_numbers.append(grn.grn_no)
        except Exception as exc:
            local.rollback()
            with lock:
                errors.append(str(exc))
        finally:
            local.close()

    threads = [threading.Thread(target=inward, args=(item_id,)) for item_id in ok_item_ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, errors
    assert len(grn_numbers) == len(set(grn_numbers))
    assert len(grn_numbers) == len(ok_item_ids)


def test_sync_backfills_existing_iqc_logs(db_session):
    session, _engine, _path = db_session
    logs = []
    for idx in range(4):
        logs.append(_make_inspection_log(session, lot_quantity=20 + idx, part_suffix=str(idx)))
    session.commit()

    result = sync_store_from_inspections(session, commit=True)
    assert result["synced_lots"] == 4
    assert result["bin_items_created"] >= 4

    lots = session.query(IqcLot).count()
    bins = session.query(StoreBinItem).count()
    assert lots == 4
    assert bins >= 4

    repeat = sync_store_from_inspections(session, commit=True)
    assert repeat["synced_lots"] == 0
    assert session.query(IqcLot).count() == 4


def test_unanimous_ratings_route_whole_lot_to_one_bin():
    allocated = _allocate_quantities(
        100,
        {"OD": "GREEN", "ID": "GREEN", "Length": "GREEN"},
        "GREEN",
    )
    assert allocated == {"OK": 100, "REJECTED": 0, "DOUBTFUL": 0}


def test_mixed_ratings_split_lot_proportionally():
    allocated = _allocate_quantities(
        100,
        {"OD": "GREEN", "ID": "RED"},
        "GREEN",
    )
    assert allocated["OK"] == 50
    assert allocated["REJECTED"] == 50
    assert allocated["DOUBTFUL"] == 0


def test_missing_lot_quantity_defaults_to_one():
    allocated = _allocate_quantities(None, {"OD": "GREEN"}, "GREEN")
    assert allocated["OK"] == 1
