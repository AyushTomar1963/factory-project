import copy

import pytest

from jobhunt import resume as resume_mod, tailor
from jobhunt.llm import LLMError

JOB = {
    "id": 1, "title": "Senior Backend Engineer", "company": "Acme",
    "description": "Python, Go, PostgreSQL, Kafka, Kubernetes, AWS. Rust is a plus. 5+ years experience.",
}


class FakeLLM:
    model = "fake"

    def __init__(self, response=None, error=False):
        self.response, self.error = response, error

    def complete_json(self, system, user):
        if self.error:
            raise LLMError("boom")
        return self.response


def test_deterministic_tailor_keeps_facts_and_reorders(master):
    original = copy.deepcopy(master)
    out = tailor.tailor(master, JOB)
    assert master == original, "master must never be mutated"
    assert out.engine == "deterministic"
    assert out.violations == []
    assert resume_mod.find_mutations(master, out.resume) == []
    assert "Rust" in out.missing and "Python" in out.matched
    assert "Rust" not in out.pitch and "Rust" not in out.cover_letter
    # most relevant Paylane bullet (Go + PostgreSQL) comes first
    assert out.resume["work"][0]["highlights"][0].startswith("Designed an idempotent payments API")
    assert len(out.linkedin_note) <= tailor.LINKEDIN_NOTE_LIMIT


def test_guard_rejects_fabrications_from_llm(master):
    src0 = master["work"][0]["highlights"]
    response = {
        "summary": "Backend engineer with 10 years of Rust experience.",  # invented number + skill
        "skills_priority": ["Kafka", "Rust"],  # Rust doesn't exist; must not be added
        "work": [
            {"index": 0, "highlights": [
                {"source": 1, "text": "Migrated batch jobs to Airflow on Kubernetes, cutting failed runs by 70%"},  # fine
                {"source": 0, "text": "Designed a payments API in Go and Rust handling 9,000 requests per second"},  # bad
                {"source": 99, "text": "Invented a bullet"},  # unknown source
            ]},
        ],
        "pitch": "I have shipped Kafka pipelines in Python on AWS. Open to a quick chat?",
        "cover_letter": "I led a team of 40 engineers.",  # invented number
        "linkedin_note": "Python and Go backend engineer interested in the role.",
        # attempts to touch immutable fields are simply ignored by construction:
        "work_name_override": "Google",
    }
    out = tailor.tailor(master, JOB, FakeLLM(response))
    assert out.engine == "llm:fake"
    assert out.resume["basics"]["summary"] == master["basics"]["summary"]
    hl = out.resume["work"][0]["highlights"]
    assert hl[0] == "Migrated batch jobs to Airflow on Kubernetes, cutting failed runs by 70%"
    assert hl[1] == src0[0], "fabricated rewrite must fall back to the original bullet"
    assert all("Rust" not in h for h in hl)
    assert out.pitch == response["pitch"]
    assert "40" not in out.cover_letter
    assert out.linkedin_note == response["linkedin_note"]
    joined = " | ".join(out.violations)
    assert "skill 'Rust'" in joined and "number '10'" in joined and "unknown source 99" in joined
    assert "Rust" not in str(out.resume["skills"])
    assert out.resume["skills"][0]["keywords"][0] in {"Kafka", "Python"}
    assert resume_mod.find_mutations(master, out.resume) == []
    assert [w["name"] for w in out.resume["work"]] == [w["name"] for w in master["work"]]


def test_rewrite_cannot_borrow_skill_from_another_job(master):
    # Kubernetes is on the resume, but not in the Shopwise Django bullet.
    response = {"work": [{"index": 1, "highlights": [
        {"source": 0, "text": "Built a Django REST service on Kubernetes backed by Elasticsearch, serving 2M daily queries"},
    ]}]}
    out = tailor.tailor(master, JOB, FakeLLM(response))
    assert out.resume["work"][1]["highlights"][0] == master["work"][1]["highlights"][0]
    assert any("Kubernetes" in v for v in out.violations)
    assert len(out.resume["work"][1]["highlights"]) >= 2


def test_llm_failure_falls_back(master):
    out = tailor.tailor(master, JOB, FakeLLM(error=True))
    assert out.engine == "deterministic"
    assert any("llm unavailable" in v for v in out.violations)


def test_find_mutations_detects_changes(master):
    t = copy.deepcopy(master)
    t["work"][0]["highlights"] = ["anything"]
    t["skills"] = []
    assert resume_mod.find_mutations(master, t) == []
    t["work"][0]["startDate"] = "2010-01"
    t["education"][0]["studyType"] = "PhD"
    assert set(resume_mod.find_mutations(master, t)) == {"work.0.startDate", "education.0.studyType"}


def test_compose_email_and_note(master):
    school = master["education"][0]["institution"]
    job = {**JOB, "season": "Summer 2027"}
    subject, body = tailor.compose_email(master, job, {"name": "Ann Lee", "first_name": "Ann"}, "Pitch.")
    assert subject == f"Summer 2027 internship - Jane Doe, {school}"
    assert body.startswith("Hi Ann,\n\nPitch.") and "jane@janedoe-careers.com" in body
    assert tailor.compose_email(master, JOB, {"name": "Ann"}, "P")[0].startswith("Internship - Jane Doe")
    note = tailor.compose_linkedin_note({"name": "Ann Lee"}, "x " * 400)
    assert len(note) <= 300 and note.startswith("Hi Ann,")


def test_internship_pitch_depends_on_source(master):
    post = {"source": "hiring_posts", "title": "Hiring interns", "season": "Winter 2026",
            "description": "We're hiring Python interns for Winter 2026"}
    out = tailor.tailor(master, post)
    assert "LinkedIn post about hiring interns" in out.pitch
    assert "a Winter 2026 internship" in out.pitch
    assert out.violations == [], "season year may be quoted back"
    direct = tailor.tailor(master, {"source": "companies", "title": "Internship", "company": "Acme"})
    assert "following what Acme is building" in direct.pitch and "an upcoming internship" in direct.pitch


def test_followup_threads_subject(master):
    subject, body = tailor.compose_followup(master, {"company": "Acme", "season": "Summer 2027"},
                                            {"name": "Ann Lee"}, "Summer 2027 internship - Jane Doe")
    assert subject == "Re: Summer 2027 internship - Jane Doe"
    assert body.startswith("Hi Ann,") and "a Summer 2027 internship at Acme" in body
    assert tailor.compose_followup(master, {}, {"name": "A"}, subject)[0] == subject


def test_validate_rejects_bad_resume():
    with pytest.raises(resume_mod.ResumeError):
        resume_mod.validate({"basics": {"name": "x"}, "work": []})
    with pytest.raises(resume_mod.ResumeError):
        resume_mod.validate({"work": []})
    student = {"basics": {"name": "x", "email": "x@y.com"}}
    resume_mod.validate(student)
    assert student["work"] == [], "students without work history are valid"
