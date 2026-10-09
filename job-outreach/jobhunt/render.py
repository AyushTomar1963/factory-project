"""Deterministic local document build: JSON Resume -> HTML -> PDF (WeasyPrint)."""
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
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def resume_html(resume: dict) -> str:
    return _env.get_template("resume.html.j2").render(r=resume)


def cover_letter_html(resume: dict, job: dict, letter: str) -> str:
    return _env.get_template("cover_letter.html.j2").render(
        r=resume, job=job, letter=letter, date=date.today().strftime("%B %d, %Y")
    )


def to_pdf(html: str, out: Path) -> Path | None:
    """Write a PDF if WeasyPrint (and its native libs) are available."""
    try:
        from weasyprint import HTML
    except (ImportError, OSError):
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_pdf(str(out))
    return out


def build(resume: dict, job: dict, letter: str, out_dir: Path) -> dict:
    name = slug(resume["basics"]["name"])
    folder = out_dir / f"{job['id']:05d}-{slug(job['company'])}-{slug(job['title'])}"
    folder.mkdir(parents=True, exist_ok=True)
    r_html = resume_html(resume)
    c_html = cover_letter_html(resume, job, letter)
    (folder / "resume.html").write_text(r_html)
    (folder / "cover_letter.html").write_text(c_html)
    (folder / "cover_letter.txt").write_text(letter)
    resume_pdf = to_pdf(r_html, folder / f"{name}-resume.pdf")
    cover_pdf = to_pdf(c_html, folder / f"{name}-cover-letter.pdf")
    return {
        "folder": str(folder),
        "resume_html": str(folder / "resume.html"),
        "resume_pdf": str(resume_pdf) if resume_pdf else None,
        "cover_pdf": str(cover_pdf) if cover_pdf else None,
    }
