from datetime import date, datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from models import (
    BIN_TYPES,
    DocumentSequence,
    Grn,
    IqcLot,
    InspectionLog,
    MaterialIssue,
    StoreBinItem,
    User,
)

STATUS_TO_BIN = {
    "GREEN": "OK",
    "RED": "REJECTED",
    "YELLOW": "DOUBTFUL",
}

RATING_TO_BIN = {
    "GREEN": "OK",
    "GO": "OK",
    "PASS": "OK",
    "RED": "REJECTED",
    "FAIL": "REJECTED",
    "REJECT": "REJECTED",
    "NO GO": "REJECTED",
    "NOGO": "REJECTED",
    "YELLOW": "DOUBTFUL",
    "HOLD": "DOUBTFUL",
    "DOUBTFUL": "DOUBTFUL",
    "MARGINAL": "DOUBTFUL",
}


def _normalize_lot_quantity(raw_quantity, overall_status: str) -> int:
    """Ensure every finalized IQC lot has a positive quantity for store routing."""
    try:
        quantity = int(raw_quantity)
    except (TypeError, ValueError):
        quantity = 0
    if quantity > 0:
        return quantity
    return 1 if overall_status else 0


def _rating_bin(rating) -> str | None:
    if rating is None:
        return None
    normalized = str(rating).strip().upper()
    if not normalized:
        return None
    return RATING_TO_BIN.get(normalized)


def _allocate_quantities(lot_quantity: int, measured_values: dict, overall_status: str) -> dict:
    """Split lot quantity across OK / REJECTED / DOUBTFUL bins."""
    lot_quantity = _normalize_lot_quantity(lot_quantity, overall_status)
    if lot_quantity <= 0:
        return {"OK": 0, "REJECTED": 0, "DOUBTFUL": 0}

    counts = {"OK": 0, "REJECTED": 0, "DOUBTFUL": 0}
    if measured_values:
        for rating in measured_values.values():
            bin_type = _rating_bin(rating)
            if bin_type:
                counts[bin_type] += 1

    total_rated = sum(counts.values())
    if total_rated == 0:
        bin_type = STATUS_TO_BIN.get(str(overall_status or "").upper(), "OK")
        counts[bin_type] = lot_quantity
        return counts

    distinct_bins = {bin_type for bin_type, count in counts.items() if count > 0}
    if len(distinct_bins) == 1:
        target_bin = next(iter(distinct_bins))
        return {
            "OK": lot_quantity if target_bin == "OK" else 0,
            "REJECTED": lot_quantity if target_bin == "REJECTED" else 0,
            "DOUBTFUL": lot_quantity if target_bin == "DOUBTFUL" else 0,
        }

    allocated = {}
    remainder = lot_quantity
    bin_order = ["OK", "REJECTED", "DOUBTFUL"]
    for idx, bin_type in enumerate(bin_order):
        if idx == len(bin_order) - 1:
            allocated[bin_type] = remainder
        else:
            share = int(lot_quantity * counts[bin_type] / total_rated)
            allocated[bin_type] = share
            remainder -= share
    return allocated


def create_store_bins_from_inspection(db: Session, log: InspectionLog) -> IqcLot:
    """Create IQC lot + store bin rows in the same transaction as inspection finalize."""
    existing = (
        db.query(IqcLot).filter(IqcLot.inspection_log_id == log.id).first()
    )
    if existing:
        return existing

    lot_quantity = _normalize_lot_quantity(log.lot_quantity, log.status)
    lot_date = log.timestamp or datetime.now(timezone.utc)
    part_no = (log.part_number or "UNKNOWN").strip().upper()

    iqc_lot = IqcLot(
        inspection_log_id=log.id,
        part_no=part_no,
        supplier=(log.supplier or "N/A").strip(),
        lot_quantity=lot_quantity,
        invoice_number=(log.invoice_number or "N/A").strip(),
        lot_date=lot_date,
        overall_status=log.status or "GREEN",
    )
    db.add(iqc_lot)
    db.flush()

    quantities = _allocate_quantities(
        lot_quantity, log.measured_values or {}, log.status or "GREEN"
    )

    for bin_type in BIN_TYPES:
        qty = quantities.get(bin_type, 0)
        if qty <= 0:
            continue
        db.add(
            StoreBinItem(
                iqc_lot_id=iqc_lot.id,
                bin_type=bin_type,
                part_no=part_no,
                supplier=(log.supplier or "N/A").strip(),
                quantity=qty,
                lot_date=lot_date,
                status="PENDING",
            )
        )

    return iqc_lot


def sync_store_from_inspections(db: Session, commit: bool = True) -> dict:
    """Backfill store bins for IQC logs finalized before store integration."""
    pending_logs = (
        db.query(InspectionLog)
        .outerjoin(IqcLot, IqcLot.inspection_log_id == InspectionLog.id)
        .filter(IqcLot.id.is_(None))
        .order_by(InspectionLog.id.asc())
        .all()
    )

    synced = 0
    bin_items_created = 0
    for log in pending_logs:
        before = db.query(StoreBinItem).count()
        create_store_bins_from_inspection(db, log)
        db.flush()
        after = db.query(StoreBinItem).count()
        synced += 1
        bin_items_created += max(after - before, 0)

    if commit and synced:
        db.commit()

    return {
        "synced_lots": synced,
        "bin_items_created": bin_items_created,
        "pending_before": len(pending_logs),
    }


def get_store_summary(db: Session) -> dict:
    """Counts for store dashboard and IQC linkage health."""
    pending_iqc = (
        db.query(InspectionLog)
        .outerjoin(IqcLot, IqcLot.inspection_log_id == InspectionLog.id)
        .filter(IqcLot.id.is_(None))
        .count()
    )
    totals = {"OK": 0, "REJECTED": 0, "DOUBTFUL": 0}
    pending_inward = {"OK": 0, "REJECTED": 0, "DOUBTFUL": 0}
    for bin_type in BIN_TYPES:
        totals[bin_type] = (
            db.query(StoreBinItem).filter(StoreBinItem.bin_type == bin_type).count()
        )
        pending_inward[bin_type] = (
            db.query(StoreBinItem)
            .filter(
                StoreBinItem.bin_type == bin_type,
                StoreBinItem.status == "PENDING",
            )
            .count()
        )

    return {
        "iqc_logs_total": db.query(InspectionLog).count(),
        "iqc_lots_total": db.query(IqcLot).count(),
        "iqc_pending_sync": pending_iqc,
        "bin_totals": totals,
        "bin_pending_inward": pending_inward,
    }


def next_document_number(db: Session, doc_type: str, prefix: str) -> str:
    """Race-safe sequential document number via atomic UPSERT increment."""
    year = datetime.now(timezone.utc).year

    result = db.execute(
        text(
            """
            INSERT INTO document_sequences (doc_type, year, last_number)
            VALUES (:doc_type, :year, 1)
            ON CONFLICT (doc_type, year)
            DO UPDATE SET last_number = document_sequences.last_number + 1
            RETURNING last_number
            """
        ),
        {"doc_type": doc_type, "year": year},
    )
    number = result.scalar_one()
    return f"{prefix}/{year}/{number:05d}"


def get_user_id(db: Session, username: str) -> int:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise ValueError(f"User not found: {username}")
    return user.id


def create_grn_from_bin(
    db: Session,
    bin_item_id: int,
    invoice_no: str,
    invoice_date: date,
    store_keeper_username: str,
) -> Grn:
    bin_item = (
        db.query(StoreBinItem).filter(StoreBinItem.id == bin_item_id).with_for_update().first()
    )
    if not bin_item:
        raise ValueError("Bin item not found")
    if bin_item.bin_type != "OK":
        raise ValueError("GRN can only be created from OK-bin items")
    if bin_item.status != "PENDING":
        raise ValueError("Bin item is not pending inward")
    if bin_item.grn_id is not None:
        raise ValueError("GRN already exists for this bin item")

    grn_no = next_document_number(db, "GRN", "GRN")
    keeper_id = get_user_id(db, store_keeper_username)

    grn = Grn(
        grn_no=grn_no,
        store_bin_item_id=bin_item.id,
        part_no=bin_item.part_no,
        supplier=bin_item.supplier,
        quantity=bin_item.quantity,
        invoice_no=invoice_no.strip(),
        invoice_date=invoice_date,
        store_keeper_id=keeper_id,
    )
    db.add(grn)
    db.flush()

    bin_item.status = "INWARDED"
    bin_item.grn_id = grn.id
    return grn


def remaining_grn_quantity(db: Session, grn_id: int) -> int:
    grn = db.query(Grn).filter(Grn.id == grn_id).first()
    if not grn:
        return 0
    issued = (
        db.query(MaterialIssue)
        .filter(MaterialIssue.grn_id == grn_id)
        .with_entities(MaterialIssue.quantity_issued)
        .all()
    )
    total_issued = sum(row[0] for row in issued)
    return grn.quantity - total_issued


def create_material_issue(
    db: Session,
    grn_id: int,
    quantity_issued: int,
    issued_to: str,
    remarks: str | None,
    issued_by_username: str,
) -> MaterialIssue:
    grn = db.query(Grn).filter(Grn.id == grn_id).with_for_update().first()
    if not grn:
        raise ValueError("GRN not found")

    remaining = remaining_grn_quantity(db, grn_id)
    if quantity_issued <= 0:
        raise ValueError("Quantity issued must be positive")
    if quantity_issued > remaining:
        raise ValueError(
            f"Quantity issued ({quantity_issued}) exceeds remaining GRN quantity ({remaining})"
        )

    issue_no = next_document_number(db, "ISSUE", "ISS")
    issuer_id = get_user_id(db, issued_by_username)

    issue = MaterialIssue(
        issue_no=issue_no,
        grn_id=grn_id,
        part_no=grn.part_no,
        quantity_issued=quantity_issued,
        issued_to=issued_to.strip(),
        remarks=remarks,
        issued_by=issuer_id,
    )
    db.add(issue)
    return issue


def serialize_bin_item(item: StoreBinItem) -> dict:
    grn_no = item.grn.grn_no if item.grn else None
    invoice_no = item.grn.invoice_no if item.grn else item.iqc_lot.invoice_number
    return {
        "id": item.id,
        "iqc_lot_id": item.iqc_lot_id,
        "bin_type": item.bin_type,
        "part_no": item.part_no,
        "supplier": item.supplier,
        "quantity": item.quantity,
        "lot_date": item.lot_date.isoformat() if item.lot_date else None,
        "status": item.status,
        "grn_id": item.grn_id,
        "grn_no": grn_no,
        "invoice_no": invoice_no,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
