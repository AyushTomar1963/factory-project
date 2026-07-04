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
    "RED": "REJECTED",
    "YELLOW": "DOUBTFUL",
}


def _allocate_quantities(lot_quantity: int, measured_values: dict, overall_status: str) -> dict:
    """Split lot quantity across OK / REJECTED / DOUBTFUL bins."""
    if lot_quantity <= 0:
        return {"OK": 0, "REJECTED": 0, "DOUBTFUL": 0}

    counts = {"OK": 0, "REJECTED": 0, "DOUBTFUL": 0}
    if measured_values:
        for rating in measured_values.values():
            bin_type = RATING_TO_BIN.get(str(rating).upper())
            if bin_type:
                counts[bin_type] += 1

    total_rated = sum(counts.values())
    if total_rated == 0:
        bin_type = STATUS_TO_BIN.get(overall_status.upper(), "OK")
        counts[bin_type] = lot_quantity
        return counts

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
    lot_quantity = log.lot_quantity or 0
    lot_date = log.timestamp or datetime.now(timezone.utc)

    iqc_lot = IqcLot(
        inspection_log_id=log.id,
        part_no=log.part_number,
        supplier=log.supplier or "N/A",
        lot_quantity=lot_quantity,
        invoice_number=log.invoice_number,
        lot_date=lot_date,
        overall_status=log.status,
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
                part_no=log.part_number,
                supplier=log.supplier or "N/A",
                quantity=qty,
                lot_date=lot_date,
                status="PENDING",
            )
        )

    return iqc_lot


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
