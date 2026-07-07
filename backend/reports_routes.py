import io
from datetime import date, datetime, time, timezone
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from deps import get_current_user, require_admin, require_store_or_admin
from models import BufferConfig, Grn, InspectionLog, MaterialIssue, StoreBinItem

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
        return datetime.combine(parsed, time.min, tzinfo=timezone.utc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date: {value}") from exc


def _end_of_day(value: datetime) -> datetime:
    return datetime.combine(value.date(), time.max, tzinfo=timezone.utc)


def _reports_access(current_user=Depends(get_current_user)):
    if current_user["role"] not in ("admin", "store_keeper", "worker"):
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user


def _fetch_iqc_report(db, start_date, end_date, part_no):
    query = db.query(InspectionLog)
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start:
        query = query.filter(InspectionLog.timestamp >= start)
    if end:
        query = query.filter(InspectionLog.timestamp <= _end_of_day(end))
    if part_no:
        query = query.filter(InspectionLog.part_number.ilike(f"%{part_no.strip()}%"))

    logs = query.order_by(InspectionLog.timestamp.desc()).all()
    rows = []
    summary = {}

    for log in logs:
        failed_qty = log.lot_quantity or 0 if log.status in ("RED", "YELLOW") else 0
        row = {
            "part_no": log.part_number,
            "date": log.timestamp.date().isoformat() if log.timestamp else None,
            "status": log.status,
            "lot_quantity": log.lot_quantity,
            "failed_quantity": failed_qty,
            "supplier": log.supplier,
            "stage": log.stage,
        }
        rows.append(row)
        key = (row["part_no"], row["date"])
        if key not in summary:
            summary[key] = {"part_no": row["part_no"], "date": row["date"], "failure_count": 0}
        if log.status in ("RED", "YELLOW"):
            summary[key]["failure_count"] += failed_qty or 1

    return {"rows": rows, "summary": list(summary.values()), "total_inspections": len(rows)}


def _fetch_store_report(db, start_date, end_date, part_no):
    query = db.query(StoreBinItem)
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start:
        query = query.filter(StoreBinItem.lot_date >= start)
    if end:
        query = query.filter(StoreBinItem.lot_date <= _end_of_day(end))
    if part_no:
        query = query.filter(StoreBinItem.part_no.ilike(f"%{part_no.strip()}%"))

    items = query.order_by(StoreBinItem.lot_date.desc()).all()
    rows = []
    summary = {}

    for item in items:
        failed_qty = item.quantity if item.bin_type in ("REJECTED", "DOUBTFUL") else 0
        row = {
            "part_no": item.part_no,
            "date": item.lot_date.date().isoformat() if item.lot_date else None,
            "bin_type": item.bin_type,
            "quantity": item.quantity,
            "failed_quantity": failed_qty,
            "status": item.status,
            "supplier": item.supplier,
        }
        rows.append(row)
        key = (row["part_no"], row["date"])
        if key not in summary:
            summary[key] = {"part_no": row["part_no"], "date": row["date"], "failure_count": 0}
        summary[key]["failure_count"] += failed_qty

    return {"rows": rows, "summary": list(summary.values()), "total_bin_items": len(rows)}


def _fetch_issue_report(db, start_date, end_date, part_no):
    query = db.query(MaterialIssue)
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if start:
        query = query.filter(MaterialIssue.created_at >= start)
    if end:
        query = query.filter(MaterialIssue.created_at <= _end_of_day(end))
    if part_no:
        query = query.filter(MaterialIssue.part_no.ilike(f"%{part_no.strip()}%"))

    issues = query.order_by(MaterialIssue.created_at.desc()).all()
    rows = []
    summary = {}
    total_issued = 0

    for issue in issues:
        qty = issue.quantity_issued or 0
        total_issued += qty
        row = {
            "issue_no": issue.issue_no,
            "grn_no": issue.grn.grn_no if issue.grn else None,
            "part_no": issue.part_no,
            "quantity_issued": qty,
            "issued_to": issue.issued_to,
            "remarks": issue.remarks or "",
            "date": issue.created_at.date().isoformat() if issue.created_at else None,
        }
        rows.append(row)
        key = row["part_no"]
        if key not in summary:
            summary[key] = {"part_no": key, "issue_count": 0, "total_issued": 0}
        summary[key]["issue_count"] += 1
        summary[key]["total_issued"] += qty

    return {
        "rows": rows,
        "summary": list(summary.values()),
        "total_issues": len(rows),
        "total_issued": total_issued,
    }


def _buffer_penetration(min_buffer, max_buffer, current_stock):
    """Return (penetration_pct, status, action) for one material line.

    Penetration % = ((Max - Current) / (Max - Min)) * 100
    Green 0-33 | Yellow 34-66 | Red >66 or below minimum buffer.
    """
    span = (max_buffer or 0) - (min_buffer or 0)
    if span <= 0:
        penetration = 0.0 if current_stock >= (max_buffer or 0) else 100.0
    else:
        penetration = ((max_buffer - current_stock) / span) * 100

    penetration = round(penetration, 1)
    below_minimum = current_stock <= (min_buffer or 0)

    if below_minimum or penetration > 66:
        status, action = "Red", "Immediate replenishment"
    elif penetration >= 34:
        status, action = "Yellow", "Monitor"
    else:
        status, action = "Green", "No action"

    return penetration, status, action


def _fetch_bpr_report(db, warehouse, part_no):
    inwarded = dict(
        db.query(Grn.part_no, func.coalesce(func.sum(Grn.quantity), 0))
        .group_by(Grn.part_no)
        .all()
    )
    issued = dict(
        db.query(
            MaterialIssue.part_no,
            func.coalesce(func.sum(MaterialIssue.quantity_issued), 0),
        )
        .group_by(MaterialIssue.part_no)
        .all()
    )

    query = db.query(BufferConfig)
    if warehouse:
        query = query.filter(BufferConfig.warehouse == warehouse.strip())
    if part_no:
        query = query.filter(BufferConfig.material_code.ilike(f"%{part_no.strip()}%"))
    configs = query.order_by(BufferConfig.material_code.asc()).all()

    rows = []
    counts = {"Green": 0, "Yellow": 0, "Red": 0}
    for cfg in configs:
        current_stock = int(inwarded.get(cfg.material_code, 0) or 0) - int(
            issued.get(cfg.material_code, 0) or 0
        )
        penetration, status, action = _buffer_penetration(
            cfg.min_buffer, cfg.max_buffer, current_stock
        )
        counts[status] += 1
        rows.append(
            {
                "material_code": cfg.material_code,
                "material_description": cfg.material_description or "",
                "warehouse": cfg.warehouse,
                "min_buffer": cfg.min_buffer,
                "max_buffer": cfg.max_buffer,
                "current_stock": current_stock,
                "penetration_pct": penetration,
                "status": status,
                "action_required": action,
            }
        )

    return {
        "rows": rows,
        "summary": [
            {"status": status, "material_count": count}
            for status, count in counts.items()
        ],
        "total_materials": len(rows),
        "status_counts": counts,
    }


@router.get("/iqc")
def iqc_report(
    db: Session = Depends(get_db),
    current_user=Depends(_reports_access),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    part_no: Optional[str] = Query(None),
):
    return _fetch_iqc_report(db, start_date, end_date, part_no)


@router.get("/store")
def store_report(
    db: Session = Depends(get_db),
    current_user=Depends(require_store_or_admin),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    part_no: Optional[str] = Query(None),
):
    return _fetch_store_report(db, start_date, end_date, part_no)


@router.get("/issue")
def issue_report(
    db: Session = Depends(get_db),
    current_user=Depends(require_store_or_admin),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    part_no: Optional[str] = Query(None),
):
    return _fetch_issue_report(db, start_date, end_date, part_no)


@router.get("/bpr")
def bpr_report(
    db: Session = Depends(get_db),
    current_user=Depends(require_store_or_admin),
    warehouse: Optional[str] = Query(None),
    part_no: Optional[str] = Query(None),
):
    return _fetch_bpr_report(db, warehouse, part_no)


_EXPORT_COLUMNS = {
    "iqc": ["part_no", "date", "failure_count"],
    "store": ["part_no", "date", "failure_count"],
    "issue": [
        "issue_no",
        "grn_no",
        "part_no",
        "quantity_issued",
        "issued_to",
        "remarks",
        "date",
    ],
    "bpr": [
        "material_code",
        "material_description",
        "warehouse",
        "min_buffer",
        "max_buffer",
        "current_stock",
        "penetration_pct",
        "status",
        "action_required",
    ],
}


@router.get("/export")
def export_report(
    db: Session = Depends(get_db),
    current_user=Depends(require_store_or_admin),
    type: str = Query(..., pattern="^(iqc|store|issue|bpr)$"),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    part_no: Optional[str] = Query(None),
    warehouse: Optional[str] = Query(None),
):
    if type == "iqc":
        data = _fetch_iqc_report(db, start_date, end_date, part_no)
        sheet_rows = data["summary"]
        filename_base = "iqc_report"
    elif type == "store":
        data = _fetch_store_report(db, start_date, end_date, part_no)
        sheet_rows = data["summary"]
        filename_base = "store_report"
    elif type == "issue":
        data = _fetch_issue_report(db, start_date, end_date, part_no)
        sheet_rows = data["rows"]
        filename_base = "issue_report"
    else:
        data = _fetch_bpr_report(db, warehouse, part_no)
        sheet_rows = data["rows"]
        filename_base = "buffer_penetration_report"

    df = pd.DataFrame(sheet_rows)
    if df.empty:
        df = pd.DataFrame(columns=_EXPORT_COLUMNS[type])

    buffer = io.BytesIO()
    if format == "xlsx":
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=type.upper())
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"{filename_base}.xlsx"
    else:
        buffer.write(df.to_csv(index=False).encode("utf-8"))
        media_type = "text/csv"
        filename = f"{filename_base}.csv"

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
