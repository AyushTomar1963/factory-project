import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional


STATUS_LABELS = {
    "GREEN": "PASS",
    "YELLOW": "HOLD / MARGINAL",
    "RED": "FAIL / REJECT",
}


def _format_measurements(measured_values: Dict[str, str]) -> str:
    if not measured_values:
        return "No parameter ratings recorded."
    lines = [f"- {name}: {rating}" for name, rating in measured_values.items()]
    return "\n".join(lines)


def build_fallback_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    status = payload.get("status", "GREEN")
    disposition = STATUS_LABELS.get(status, status)
    measured = payload.get("measured_values") or {}

    return {
        "report_id": now.strftime("RIQ-%Y%m%d-%H%M%S"),
        "company": "Rushab Industries",
        "title": "Factory Quality Inspection Report",
        "inspection_date": now.isoformat(),
        "disposition": disposition,
        "executive_summary": (
            f"Part {payload.get('part_number', 'N/A')} ({payload.get('part_name', 'N/A')}) "
            f"was inspected at {payload.get('current_stage', 'N/A')} with final disposition {disposition}."
        ),
        "sections": [
            {
                "heading": "1. Part Identification",
                "body": (
                    f"Part Number: {payload.get('part_number', 'N/A')}\n"
                    f"Part Name: {payload.get('part_name', 'N/A')}\n"
                    f"Inspection Stage: {payload.get('current_stage', 'N/A')}"
                ),
            },
            {
                "heading": "2. Lot & Supplier Details",
                "body": (
                    f"Supplier: {payload.get('supplier') or 'N/A'}\n"
                    f"Invoice Number: {payload.get('invoice_number') or 'N/A'}\n"
                    f"Lot Quantity: {payload.get('lot_quantity') or 'N/A'}\n"
                    f"Checking Frequency: {payload.get('checking_frequency') or 'N/A'}%"
                ),
            },
            {
                "heading": "3. Parameter Ratings",
                "body": _format_measurements(measured),
            },
            {
                "heading": "4. Inspector Remarks",
                "body": payload.get("worker_remark") or "No additional remarks.",
            },
            {
                "heading": "5. Quality Disposition",
                "body": (
                    f"Final Status: {disposition}\n"
                    f"Inspector: {payload.get('logged_by', 'N/A')}\n"
                    "Recommended Action: Review measurements and follow standard rework / hold procedures as applicable."
                ),
            },
        ],
        "recommendations": [
            "Retain this report with the lot traceability record.",
            "Escalate to supervisor if disposition is HOLD or FAIL.",
        ],
        "generated_by": "Rushab Industries QA System",
    }


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


def generate_inspection_report(gemini_model, payload: Dict[str, Any]) -> Dict[str, Any]:
    fallback = build_fallback_report(payload)
    if not gemini_model:
        return fallback

    status = payload.get("status", "GREEN")
    disposition = STATUS_LABELS.get(status, status)
    measured = _format_measurements(payload.get("measured_values") or {})
    now = datetime.now(timezone.utc).isoformat()

    prompt = f"""You are a senior factory QA documentation specialist for Rushab Industries.
Create a formal, systematic inspection report as valid JSON only (no markdown fences).

Input data:
- Part Number: {payload.get('part_number')}
- Part Name: {payload.get('part_name')}
- Stage: {payload.get('current_stage')}
- Supplier: {payload.get('supplier') or 'N/A'}
- Invoice: {payload.get('invoice_number') or 'N/A'}
- Lot Qty: {payload.get('lot_quantity') or 'N/A'}
- Checking Frequency: {payload.get('checking_frequency') or 'N/A'}%
- Parameter Ratings:
{measured}
- Final Status Code: {status} ({disposition})
- Worker Remark: {payload.get('worker_remark') or 'None'}
- Inspector: {payload.get('logged_by') or 'N/A'}
- Timestamp: {now}

Return JSON with exactly these keys:
{{
  "report_id": "RIQ-YYYYMMDD-HHMMSS style string",
  "company": "Rushab Industries",
  "title": "Factory Quality Inspection Report",
  "inspection_date": "{now}",
  "disposition": "{disposition}",
  "executive_summary": "2-3 sentence management summary",
  "sections": [
    {{"heading": "section title", "body": "detailed paragraph or bullet text"}}
  ],
  "recommendations": ["action item 1", "action item 2"],
  "generated_by": "Rushab Industries QA System (Gemini AI)"
}}

Include at least these sections: Part Identification, Lot Traceability, Inspection Method & Stage,
Parameter Assessment, Findings & Remarks, Final Disposition & Corrective Actions.
Use professional industrial QA language. Be factual; do not invent measurements beyond the input."""

    try:
        response = gemini_model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        parsed = _extract_json(response.text or "")
        if not parsed:
            return fallback

        parsed.setdefault("company", "Rushab Industries")
        parsed.setdefault("title", "Factory Quality Inspection Report")
        parsed.setdefault("disposition", disposition)
        parsed.setdefault("inspection_date", now)
        parsed.setdefault("report_id", fallback["report_id"])
        parsed.setdefault("recommendations", fallback["recommendations"])
        parsed.setdefault("generated_by", "Rushab Industries QA System (Gemini AI)")
        if "sections" not in parsed or not isinstance(parsed["sections"], list):
            parsed["sections"] = fallback["sections"]
        if "executive_summary" not in parsed:
            parsed["executive_summary"] = fallback["executive_summary"]
        return parsed
    except Exception:
        return fallback
