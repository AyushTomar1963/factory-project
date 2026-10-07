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


def company_name(payload: Dict[str, Any]) -> str:
    name = str(payload.get("company") or "").strip()
    return name or "Rushab Industries"


def _report_prefix(company: str) -> str:
    return "NBE" if company.lower().startswith("nbe") else "RIQ"


def _replace_other_company(value: str, company: str) -> str:
    if "rushab" in company.lower():
        return value
    value = re.sub(
        r"Rushab Industries QA System \(Gemini AI\)",
        f"{company} QA System",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"Rushab Industries QA System",
        f"{company} QA System",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"Rushab Industries", company, value, flags=re.IGNORECASE)
    return re.sub(r"\bRushab\b", "NBE Motors", value, flags=re.IGNORECASE)


def _apply_company(value: Any, company: str) -> Any:
    if isinstance(value, str):
        return _replace_other_company(value, company)
    if isinstance(value, list):
        return [_apply_company(item, company) for item in value]
    if isinstance(value, dict):
        return {key: _apply_company(item, company) for key, item in value.items()}
    return value


def _stamp_company(report: Dict[str, Any], company: str) -> Dict[str, Any]:
    if "rushab" in company.lower():
        report["company"] = company
        return report
    stamped = _apply_company(report, company)
    stamped["company"] = company
    stamped["generated_by"] = f"{company} QA System"
    report_id = str(stamped.get("report_id") or "")
    if report_id.startswith("RIQ-"):
        stamped["report_id"] = "NBE-" + report_id[4:]
    return stamped


def build_fallback_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    status = payload.get("status", "GREEN")
    disposition = STATUS_LABELS.get(status, status)
    measured = payload.get("measured_values") or {}
    company = company_name(payload)

    return _stamp_company({
        "report_id": now.strftime(f"{_report_prefix(company)}-%Y%m%d-%H%M%S"),
        "company": company,
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
        "generated_by": f"{company} QA System",
    }, company)


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
    company = company_name(payload)
    other_company = ""
    if "rushab" not in company.lower():
        other_company = (
            ' Never write "Rushab" or "Rushab Industries". '
            "That name belongs to a different business and must not appear anywhere in this report."
        )

    prompt = f"""You are a senior factory QA documentation specialist for {company}.
The company on this report is exactly "{company}".{other_company}
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
  "report_id": "{_report_prefix(company)}-YYYYMMDD-HHMMSS style string",
  "company": "{company}",
  "title": "Factory Quality Inspection Report",
  "inspection_date": "{now}",
  "disposition": "{disposition}",
  "executive_summary": "2-3 sentence management summary",
  "sections": [
    {{"heading": "section title", "body": "detailed paragraph or bullet text"}}
  ],
  "recommendations": ["action item 1", "action item 2"],
  "generated_by": "{company} QA System"
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

        parsed.setdefault("company", company)
        parsed.setdefault("title", "Factory Quality Inspection Report")
        parsed.setdefault("disposition", disposition)
        parsed.setdefault("inspection_date", now)
        parsed.setdefault("report_id", fallback["report_id"])
        parsed.setdefault("recommendations", fallback["recommendations"])
        parsed.setdefault("generated_by", f"{company} QA System")
        if "sections" not in parsed or not isinstance(parsed["sections"], list):
            parsed["sections"] = fallback["sections"]
        if "executive_summary" not in parsed:
            parsed["executive_summary"] = fallback["executive_summary"]
        return _stamp_company(parsed, company)
    except Exception:
        return fallback
