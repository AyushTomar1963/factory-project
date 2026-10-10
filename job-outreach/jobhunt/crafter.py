"""Resume crafter: turn a PDF or pasted resume into the JSON Resume master.

The LLM only restructures; every resulting claim is then checked against the
source text so it cannot add skills or numbers that weren't in your resume.
"""
from __future__ import annotations

import io
import json

from . import keywords, resume as resume_mod
from .llm import LLMClient, LLMError

IMPORT_PROMPT = """Convert the resume text into JSON Resume format (https://jsonresume.org/schema).
Copy facts verbatim. Do not add, infer or embellish anything: no new skills, numbers, employers,
dates or outcomes. Dates as YYYY-MM or YYYY. Use "" or omit fields that are not present.

Return one JSON object with keys:
basics {name, label, email, phone, url, summary, location {city, region, countryCode}, profiles [{network, url}]},
education [{institution, area, studyType, startDate, endDate, score, courses []}],
work [{name, position, startDate, endDate, location, highlights []}],
projects [{name, description, url, highlights [], keywords []}],
skills [{name, keywords []}],
awards [{title, date, awarder}],
certificates [{name, issuer, date}].
"Expected" graduation dates go in education.endDate. Internships go in work."""


class CraftError(ValueError):
    pass


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as exc:  # pypdf raises many types for malformed files
        raise CraftError(f"could not read that PDF: {exc}") from exc
    if not text.strip():
        raise CraftError("that PDF has no extractable text (is it a scanned image?)")
    return text


def unsupported_claims(text: str, data: dict) -> list[str]:
    source_skills = set(keywords.extract(text))
    source_nums = keywords.numbers(text)
    corpus = resume_mod.corpus(data)
    bad = [f"skill '{s}'" for s in keywords.extract(corpus) if s not in source_skills]
    bad += [f"number '{n}'" for n in sorted(keywords.numbers(corpus) - source_nums)]
    return bad


def import_text(text: str, llm: LLMClient | None) -> tuple[dict, list[str]]:
    """Returns (resume, warnings)."""
    if not text.strip():
        raise CraftError("no resume text provided")
    if llm is None:
        raise CraftError("importing needs LLM_API_KEY; or paste JSON Resume directly into the editor")
    try:
        data = llm.complete_json(IMPORT_PROMPT, text[:30000], temperature=0)
    except LLMError as exc:
        raise CraftError(str(exc)) from exc
    data = normalise(data)
    try:
        resume_mod.validate(data)
    except resume_mod.ResumeError as exc:
        raise CraftError(f"imported resume is incomplete: {exc}. Fix it in the editor.") from exc
    return data, unsupported_claims(text, data)


def normalise(data: dict) -> dict:
    data = dict(data or {})
    data.setdefault("basics", {})
    for key in ("work", "education", "projects", "skills", "awards", "certificates"):
        if not isinstance(data.get(key), list):
            data[key] = []
    for w in data["work"]:
        if not isinstance(w.get("highlights"), list):
            w["highlights"] = []
    data["work"] = [w for w in data["work"] if w.get("name") and w.get("position")]
    return data


def parse_json(text: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CraftError(f"invalid JSON: {exc}") from exc
    data = normalise(data)
    try:
        resume_mod.validate(data)
    except resume_mod.ResumeError as exc:
        raise CraftError(str(exc)) from exc
    return data
