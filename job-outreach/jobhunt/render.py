"""Deterministic document build: JSON Resume -> HTML -> PDF bytes (WeasyPrint)."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)

_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _ym(value: str | None) -> str:
    if not value:
        return ""
    m = re.match(r"(\d{4})(?:-(\d{2}))?", value)
    if not m:
        return value
    year, month = m.groups()
    return f"{_MONTHS[int(month) - 1]} {year}" if month else year


_env.filters["ym"] = _ym


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:60]


def is_student(resume: dict) -> bool:
    label = (resume.get("basics", {}).get("label") or "").lower()
    work = resume.get("work") or []
    return ("student" in label or "intern" in label or not work
            or all("intern" in (w.get("position") or "").lower() for w in work))


def resume_html(resume: dict) -> str:
    return _env.get_template("resume.html.j2").render(r=resume, student=is_student(resume))


def cover_letter_html(resume: dict, job: dict, letter: str) -> str:
    return _env.get_template("cover_letter.html.j2").render(
        r=resume, job=job, letter=letter, date=date.today().strftime("%B %d, %Y")
    )


def to_pdf(html: str) -> bytes | None:
    """PDF bytes, or None if WeasyPrint's native libraries are missing."""
    try:
        from weasyprint import HTML
    except (ImportError, OSError):
        return None
    return HTML(string=html).write_pdf()


def pdf_filename(resume: dict, kind: str = "resume") -> str:
    return f"{slug(resume['basics']['name'])}-{kind}.pdf"


def build(resume: dict, job: dict, letter: str) -> dict:
    r_html = resume_html(resume)
    return {
        "resume_html": r_html,
        "resume_pdf": to_pdf(r_html),
        "cover_pdf": to_pdf(cover_letter_html(resume, job, letter)),
    }
