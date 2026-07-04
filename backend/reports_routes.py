import io
from datetime import date, datetime, time, timezone
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from deps import get_current_user, require_admin, require_store_or_admin
from models import Grn, InspectionLog, MaterialIssue, StoreBinItem

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


@router.get("/export")
def export_report(
    db: Session = Depends(get_db),
    current_user=Depends(require_store_or_admin),
    type: str = Query(..., pattern="^(iqc|store)$"),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    part_no: Optional[str] = Query(None),
):
    if type == "iqc":
        data = _fetch_iqc_report(db, start_date, end_date, part_no)
        sheet_rows = data["summary"]
        filename_base = "iqc_report"
    else:
        data = _fetch_store_report(db, start_date, end_date, part_no)
        sheet_rows = data["summary"]
        filename_base = "store_report"

    df = pd.DataFrame(sheet_rows)
    if df.empty:
        df = pd.DataFrame(columns=["part_no", "date", "failure_count"])

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
