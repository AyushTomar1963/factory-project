from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from database import get_db
from deps import require_store_or_admin
from models import Grn, MaterialIssue, StoreBinItem
from store_service import (
    create_grn_from_bin,
    create_material_issue,
    remaining_grn_quantity,
    serialize_bin_item,
)

router = APIRouter(prefix="/api/store", tags=["store"])

BIN_PATH_MAP = {
    "ok": "OK",
    "rejected": "REJECTED",
    "doubtful": "DOUBTFUL",
}


class InwardRequest(BaseModel):
    invoice_no: str = Field(min_length=1)
    invoice_date: date


class IssueRequest(BaseModel):
    grn_id: int
    quantity_issued: int = Field(gt=0)
    issued_to: str = Field(min_length=1)
    remarks: Optional[str] = None


@router.get("/bins/{bin_slug}")
def list_bins(
    bin_slug: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_store_or_admin),
):
    bin_type = BIN_PATH_MAP.get(bin_slug.lower())
    if not bin_type:
        raise HTTPException(status_code=404, detail="Unknown bin type")

    items = (
        db.query(StoreBinItem)
        .options(joinedload(StoreBinItem.grn), joinedload(StoreBinItem.iqc_lot))
        .filter(StoreBinItem.bin_type == bin_type)
        .order_by(StoreBinItem.created_at.desc())
        .all()
    )
    return {"bin_type": bin_type, "items": [serialize_bin_item(item) for item in items]}


@router.get("/bin/{bin_item_id}")
def get_bin_item(
    bin_item_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_store_or_admin),
):
    item = db.query(StoreBinItem).filter(StoreBinItem.id == bin_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Bin item not found")
    data = serialize_bin_item(item)
    data["iqc_lot"] = {
        "id": item.iqc_lot.id,
        "part_no": item.iqc_lot.part_no,
        "supplier": item.iqc_lot.supplier,
        "lot_quantity": item.iqc_lot.lot_quantity,
        "invoice_number": item.iqc_lot.invoice_number,
        "overall_status": item.iqc_lot.overall_status,
        "lot_date": item.iqc_lot.lot_date.isoformat() if item.iqc_lot.lot_date else None,
    }
    return data


@router.post("/inward/{bin_item_id}")
def inward_bin_item(
    bin_item_id: int,
    body: InwardRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_store_or_admin),
):
    try:
        grn = create_grn_from_bin(
            db,
            bin_item_id,
            body.invoice_no,
            body.invoice_date,
            current_user["username"],
        )
        db.commit()
        db.refresh(grn)
        return {
            "message": "GRN created",
            "grn_no": grn.grn_no,
            "grn_id": grn.id,
            "part_no": grn.part_no,
            "quantity": grn.quantity,
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/grns")
def list_grns(
    db: Session = Depends(get_db),
    current_user=Depends(require_store_or_admin),
    part_no: Optional[str] = Query(None),
):
    query = db.query(Grn).order_by(Grn.created_at.desc())
    if part_no:
        query = query.filter(Grn.part_no.ilike(f"%{part_no.strip()}%"))
    grns = query.all()
    results = []
    for grn in grns:
        remaining = remaining_grn_quantity(db, grn.id)
        results.append(
            {
                "id": grn.id,
                "grn_no": grn.grn_no,
                "part_no": grn.part_no,
                "supplier": grn.supplier,
                "quantity": grn.quantity,
                "remaining_quantity": remaining,
                "invoice_no": grn.invoice_no,
                "invoice_date": grn.invoice_date.isoformat(),
                "created_at": grn.created_at.isoformat() if grn.created_at else None,
            }
        )
    return {"grns": results}


@router.post("/issue")
def issue_material(
    body: IssueRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_store_or_admin),
):
    try:
        issue = create_material_issue(
            db,
            body.grn_id,
            body.quantity_issued,
            body.issued_to,
            body.remarks,
            current_user["username"],
        )
        db.commit()
        db.refresh(issue)
        return {
            "message": "Material issued",
            "issue_no": issue.issue_no,
            "issue_id": issue.id,
            "remaining_quantity": remaining_grn_quantity(db, body.grn_id),
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
