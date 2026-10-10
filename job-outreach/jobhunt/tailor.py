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

SYSTEM_PROMPT = """You tailor a student's existing resume for one internship opportunity: a job posting,
a LinkedIn post by someone hiring interns, or a direct inquiry to a company.

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
  "pitch": "cold email body to a founder/engineering lead asking about an internship for the given season, under 120 words, specific to the company and role, no greeting and no sign-off, ends with a low-pressure ask",
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
    def __init__(self, master: dict, job_description: str, extra_allowed: str = ""):
        self.master = master
        self.corpus = resume_mod.corpus(master)
        self.corpus_skills = set(keywords.extract(self.corpus))
        # Numbers from the role title and season ("Summer 2027") may be quoted back.
        self.corpus_numbers = keywords.numbers(self.corpus) | keywords.numbers(extra_allowed)
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

def _school(master: dict) -> str | None:
    edu = master.get("education") or []
    return edu[0].get("institution") if edu else None


def _template_texts(master: dict, job: dict, matched: list[str]) -> dict:
    b = master["basics"]
    company = job.get("company") or "your team"
    season = f"a {job['season']}" if job.get("season") else "an upcoming"
    src = job.get("source")
    if src == "hiring_posts":
        hook = "I saw the LinkedIn post about hiring interns" + (f" at {job['company']}" if job.get("company") else "")
    elif src == "linkedin_jobs":
        hook = f"I saw the {job['title']} opening"
    else:
        hook = f"I've been following what {company} is building"
    skills = _human_list(matched[:4]) or "software engineering"
    school = _school(master)
    who = f"a student at {school}" if school else (b.get("label") or "a student").lower()
    achievement = _top_achievement(master, set(matched)) or ""
    pitch = (
        f"I'm {who} looking for {season} internship and I'd love to work with {company}. "
        f"{hook}, and it lines up with what I've been working on: {skills}. "
        f"{achievement} "
        f"I've attached a one-page resume. If there's room for an intern this "
        f"{job['season'].split()[0].lower() if job.get('season') else 'cycle'}, "
        f"would you be open to a quick 15-minute chat, or could you point me to the right person?"
    ).replace("  ", " ").strip()
    cover = (
        f"I'm writing to ask about {season.split(' ', 1)[1]} internship opportunities at {company}. "
        + (f"In brief, my background: {b['summary'].strip()}" if b.get("summary") else "")
        + "\n\n"
        + f"Most of my recent work has been in {skills}. {achievement}\n\n"
        f"I'd be glad to contribute to {company} as an intern and would welcome a short conversation. Thank you for your time."
    ).replace("  ", " ").strip()
    note = f"I'm {who} interested in {season.split(' ', 1)[1]} internships at {company}; I work with {_human_list(matched[:3]) or 'software'}. Would love to connect."
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

    guard = Guard(master, description, f"{job['title']} {job.get('season') or ''}")
    engine = "deterministic"
    proposal = _deterministic(master, job, job_kw)
    texts = _template_texts(master, job, matched)

    if llm is not None:
        user = json.dumps({
            "opportunity": {"source": job.get("source"), "title": job["title"], "company": job.get("company"),
                            "season": job.get("season"), "description": description[:12000]},
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
    name = master["basics"]["name"]
    school = _school(master)
    season = job.get("season")
    head = f"{season} internship" if season else "Internship"
    subject = f"{head} - {name}" + (f", {school}" if school else "")
    body = f"Hi {first},\n\n{pitch}\n\nBest,\n{_signature(master)}"
    return subject, body


def compose_followup(master: dict, job: dict, contact: dict, original_subject: str) -> tuple[str, str]:
    first = (contact.get("first_name") or contact.get("name", "").split(" ")[0] or "there").strip()
    company = job.get("company") or "your team"
    season = f"a {job['season']}" if job.get("season") else "an upcoming"
    subject = original_subject if original_subject.lower().startswith("re:") else f"Re: {original_subject}"
    body = (
        f"Hi {first},\n\nJust bringing this back to the top of your inbox. I'd still love to be considered for "
        f"{season} internship at {company}, and I've attached my resume again in case it's useful. "
        f"Totally understand if the timing isn't right.\n\nThanks,\n{master['basics']['name']}"
    )
    return subject, body


def compose_linkedin_note(contact: dict, note: str) -> str:
    first = (contact.get("first_name") or contact.get("name", "").split(" ")[0]).strip()
    text = f"Hi {first}, {note}" if first else note
    if len(text) > LINKEDIN_NOTE_LIMIT:
        text = text[: LINKEDIN_NOTE_LIMIT - 3].rsplit(" ", 1)[0] + "..."
    return text
