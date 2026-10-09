"""Job-specific resume and message tailoring with an anti-fabrication guard.

The LLM never edits the resume directly. It returns *proposals* that reference
existing master-resume bullets by index; the tailored resume is then rebuilt
from the master, so employers, titles, dates and education cannot change by
construction. Every free-text proposal is checked for skills or numbers that
do not appear in the candidate's own material, and rejected proposals fall
back to the original text.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import keywords, resume as resume_mod
from .llm import LLMClient, LLMError

LINKEDIN_NOTE_LIMIT = 300
PITCH_WORD_LIMIT = 170

SYSTEM_PROMPT = """You tailor a candidate's existing resume to one job posting.

HARD RULES (violations are discarded automatically):
- Never invent skills, tools, employers, titles, dates, degrees, metrics or outcomes.
- Every rewritten bullet must reference the index of the ORIGINAL bullet it rephrases
  and must stay factually equivalent to it. Do not add technologies that the original
  bullet does not mention. Keep every number exactly as written in the original.
- You may reorder bullets, drop weak bullets, and rephrase wording to mirror the
  job's vocabulary where the candidate genuinely did that work.
- Summary, cover letter, pitch and note may only claim things present in the resume.
- Plain text only. No markdown, no emojis, no placeholders like [Company].

Return a JSON object with exactly these keys:
{
  "summary": "2-3 sentence professional summary",
  "skills_priority": ["skill names copied verbatim from the resume skills, most relevant first"],
  "work": [{"index": <work index>, "highlights": [{"source": <bullet index>, "text": "rephrased bullet"}]}],
  "cover_letter": "3 short paragraphs, no greeting line and no sign-off",
  "pitch": "cold email body for a hiring manager, under 140 words, no greeting and no sign-off, ends with a low-pressure ask",
  "linkedin_note": "connection note under 280 characters, no greeting"
}"""


@dataclass
class TailorResult:
    resume: dict
    cover_letter: str
    pitch: str
    linkedin_note: str
    job_keywords: list[str]
    matched: list[str]
    missing: list[str]
    engine: str
    violations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- guard

class Guard:
    def __init__(self, master: dict, job_description: str):
        self.master = master
        self.corpus = resume_mod.corpus(master)
        self.corpus_skills = set(keywords.extract(self.corpus))
        self.corpus_numbers = keywords.numbers(self.corpus)
        self.job_skills = set(keywords.extract(job_description))
        self.violations: list[str] = []

    def unsupported(self, text: str, allowed_text: str | None = None) -> list[str]:
        if allowed_text is None:
            skills, nums = self.corpus_skills, self.corpus_numbers
        else:
            skills, nums = set(keywords.extract(allowed_text)), keywords.numbers(allowed_text)
        bad = [f"skill '{s}'" for s in keywords.extract(text) if s not in skills]
        bad += [f"number '{n}'" for n in sorted(keywords.numbers(text) - nums)]
        return bad

    def check(self, label: str, text: str, allowed_text: str | None = None) -> bool:
        bad = self.unsupported(text, allowed_text)
        if bad:
            self.violations.append(f"{label}: unsupported {', '.join(bad)}")
            return False
        return True


# ---------------------------------------------------------------- helpers

def _relevance(text: str, job_kw: set[str]) -> int:
    return sum(1 for k in keywords.extract(text) if k in job_kw)


def _reorder_skills(skills: list[dict], job_kw: set[str], priority: list[str] | None = None) -> list[dict]:
    prio = [p.lower() for p in (priority or [])]

    def kw_rank(k: str) -> tuple:
        lk = k.lower()
        in_prio = prio.index(lk) if lk in prio else len(prio)
        hit = any(c in job_kw for c in keywords.extract(k))
        return (in_prio, not hit)

    out = []
    for group in skills:
        g = dict(group)
        g["keywords"] = sorted(group.get("keywords", []), key=kw_rank)
        out.append(g)

    def group_rank(g: dict) -> tuple:
        names = [g.get("name", "").lower(), *[k.lower() for k in g.get("keywords", [])]]
        in_prio = min((prio.index(n) for n in names if n in prio), default=len(prio))
        hits = _relevance(" ".join([g.get("name", ""), *g.get("keywords", [])]), job_kw)
        return (in_prio, -hits)

    return sorted(out, key=group_rank)


def _first_name(master: dict) -> str:
    return master["basics"]["name"].split()[0]


def _signature(master: dict) -> str:
    b = master["basics"]
    lines = [b["name"]]
    if b.get("label"):
        lines.append(b["label"])
    contact = [b.get("email", ""), b.get("phone", "")]
    for p in b.get("profiles", []):
        if p.get("url"):
            contact.append(p["url"])
    if b.get("url"):
        contact.append(b["url"])
    lines.append(" | ".join(c for c in contact if c))
    return "\n".join(lines)


def _top_achievement(master: dict, job_kw: set[str]) -> str | None:
    best, best_score = None, -1
    for w in master.get("work", []):
        for h in w.get("highlights", []):
            s = _relevance(h, job_kw) * 2 + (1 if keywords.numbers(h) else 0)
            if s > best_score:
                best, best_score = (w, h), s
    if not best:
        return None
    w, h = best
    h = h.rstrip(".")
    if not h:
        return None
    if len(h) > 1 and h[1].islower():
        h = h[0].lower() + h[1:]
    return f"At {w['name']}, I {h}."


def _human_list(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" and {items[-1]}"


# ---------------------------------------------------------------- deterministic engine

def _template_texts(master: dict, job: dict, matched: list[str]) -> dict:
    b = master["basics"]
    role, company = job["title"], job["company"]
    skills = _human_list(matched[:4]) or "the core skills in the posting"
    label = b.get("label") or "engineer"
    achievement = _top_achievement(master, set(matched)) or ""
    pitch = (
        f"I saw the {role} opening at {company} and wanted to reach out directly. "
        f"I'm a {label.lower()} whose day-to-day work covers {skills}, which lines up closely with what the role asks for. "
        f"{achievement} "
        f"I've attached a resume tailored to the position. "
        f"Would you be open to a short call, or could you point me to the right person on the team?"
    ).replace("  ", " ").strip()
    cover = (
        f"I'm writing to express my interest in the {role} position at {company}. "
        + (f"In brief, my background: {b['summary'].strip()}" if b.get("summary") else "")
        + "\n\n"
        + f"The role emphasises {skills}, which is where most of my recent work has been. {achievement}\n\n"
        f"I'd welcome the chance to discuss how I could contribute to {company}. Thank you for your time and consideration."
    ).replace("  ", " ").strip()
    note = f"I'm interested in the {role} role at {company}; my background is in {_human_list(matched[:3]) or label.lower()}. Would love to connect."
    return {"pitch": pitch, "cover_letter": cover, "linkedin_note": note}


def _deterministic(master: dict, job: dict, job_kw: set[str]) -> dict:
    work = []
    for i, w in enumerate(master.get("work", [])):
        order = sorted(range(len(w.get("highlights", []))), key=lambda j: -_relevance(w["highlights"][j], job_kw))
        work.append({"index": i, "highlights": [{"source": j, "text": w["highlights"][j]} for j in order]})
    return {"summary": master["basics"].get("summary", ""), "skills_priority": [], "work": work}


# ---------------------------------------------------------------- main entry

def tailor(master: dict, job: dict, llm: LLMClient | None = None) -> TailorResult:
    description = job.get("description") or ""
    job_kw_list = keywords.extract(f"{job['title']}\n{description}")
    job_kw = set(job_kw_list)
    cand_kw = resume_mod.candidate_keywords(master)
    matched = [k for k in job_kw_list if k in cand_kw]
    missing = [k for k in job_kw_list if k not in cand_kw]

    guard = Guard(master, description)
    engine = "deterministic"
    proposal = _deterministic(master, job, job_kw)
    texts = _template_texts(master, job, matched)

    if llm is not None:
        user = json.dumps({
            "job": {"title": job["title"], "company": job["company"], "description": description[:12000]},
            "candidate_resume": master,
            "skills_candidate_has_that_job_wants": matched,
            "skills_job_wants_that_candidate_lacks_DO_NOT_CLAIM": missing,
        }, ensure_ascii=False)
        try:
            proposal = llm.complete_json(SYSTEM_PROMPT, user)
            engine = f"llm:{llm.model}"
        except LLMError as exc:
            guard.violations.append(f"llm unavailable, used deterministic engine ({exc})")

    tailored = resume_mod.clone(master)

    # summary
    summary = str(proposal.get("summary") or "").strip()
    if summary and summary != master["basics"].get("summary", "") and guard.check("summary", summary):
        tailored["basics"]["summary"] = summary

    # work highlights: rebuilt from master, only by reference
    by_index = {}
    for item in proposal.get("work") or []:
        if isinstance(item, dict) and isinstance(item.get("index"), int):
            by_index[item["index"]] = item.get("highlights") or []
    for i, w in enumerate(master.get("work", [])):
        source = w.get("highlights", [])
        if i not in by_index or not source:
            continue
        chosen, used = [], set()
        for h in by_index[i]:
            if not isinstance(h, dict):
                continue
            j = h.get("source")
            if not isinstance(j, int) or not 0 <= j < len(source) or j in used:
                guard.violations.append(f"work[{i}]: bullet references unknown source {j!r}")
                continue
            text = str(h.get("text") or "").strip() or source[j]
            # A rewrite may only use skills/numbers from its own original bullet.
            if text != source[j] and not guard.check(f"work[{i}].highlights[{j}]", text, source[j]):
                text = source[j]
            chosen.append(text)
            used.add(j)
        if len(chosen) < min(2, len(source)):
            chosen += [source[j] for j in range(len(source)) if j not in used][: min(2, len(source)) - len(chosen)]
        tailored["work"][i]["highlights"] = chosen

    # skills: reorder only, never add
    if master.get("skills"):
        prio = [p for p in proposal.get("skills_priority") or [] if isinstance(p, str)]
        tailored["skills"] = _reorder_skills(master["skills"], job_kw, prio)

    # free-text messages
    for key in ("cover_letter", "pitch", "linkedin_note"):
        candidate = str(proposal.get(key) or "").strip()
        if candidate and guard.check(key, candidate):
            texts[key] = candidate

    if len(texts["pitch"].split()) > PITCH_WORD_LIMIT:
        guard.violations.append("pitch: too long, used template")
        texts["pitch"] = _template_texts(master, job, matched)["pitch"]
    if len(texts["linkedin_note"]) > LINKEDIN_NOTE_LIMIT - 20:
        texts["linkedin_note"] = texts["linkedin_note"][: LINKEDIN_NOTE_LIMIT - 23].rsplit(" ", 1)[0] + "..."

    mutations = resume_mod.find_mutations(master, tailored)
    if mutations:  # should be impossible; refuse rather than ship altered facts
        raise AssertionError(f"tailoring mutated immutable fields: {mutations}")
    _assert_skills_subset(master, tailored)

    return TailorResult(
        resume=tailored,
        cover_letter=texts["cover_letter"],
        pitch=texts["pitch"],
        linkedin_note=texts["linkedin_note"],
        job_keywords=job_kw_list,
        matched=matched,
        missing=missing,
        engine=engine,
        violations=guard.violations,
    )


def _assert_skills_subset(master: dict, tailored: dict) -> None:
    before = sorted((g.get("name"), tuple(sorted(g.get("keywords", [])))) for g in master.get("skills", []))
    after = sorted((g.get("name"), tuple(sorted(g.get("keywords", [])))) for g in tailored.get("skills", []))
    if before != after:
        raise AssertionError("tailoring changed the skills inventory")


def compose_email(master: dict, job: dict, contact: dict, pitch: str) -> tuple[str, str]:
    first = (contact.get("first_name") or contact.get("name", "").split(" ")[0] or "there").strip()
    subject = f"{job['title']} at {job['company']} - {master['basics']['name']}"
    body = f"Hi {first},\n\n{pitch}\n\nBest,\n{_signature(master)}"
    return subject, body


def compose_linkedin_note(contact: dict, note: str) -> str:
    first = (contact.get("first_name") or contact.get("name", "").split(" ")[0]).strip()
    text = f"Hi {first}, {note}" if first else note
    if len(text) > LINKEDIN_NOTE_LIMIT:
        text = text[: LINKEDIN_NOTE_LIMIT - 3].rsplit(" ", 1)[0] + "..."
    return text
