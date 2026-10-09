"""Master resume handling (JSON Resume schema)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from . import keywords

# Paths inside a tailored resume that tailoring is allowed to change.
# Everything else must be byte-identical to the master.
MUTABLE_PATHS = {("basics", "summary"), ("work", "*", "highlights"), ("skills",)}

REQUIRED_TOP = ("basics", "work")


class ResumeError(ValueError):
    pass


def load(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text())
    validate(data)
    return data


def validate(data: dict) -> None:
    for key in REQUIRED_TOP:
        if key not in data:
            raise ResumeError(f"master resume is missing '{key}'")
    basics = data["basics"]
    for key in ("name", "email"):
        if not basics.get(key):
            raise ResumeError(f"basics.{key} is required")
    for i, w in enumerate(data["work"]):
        for key in ("name", "position", "startDate"):
            if not w.get(key):
                raise ResumeError(f"work[{i}].{key} is required")
        if not isinstance(w.get("highlights", []), list):
            raise ResumeError(f"work[{i}].highlights must be a list")


def work_text(entry: dict) -> str:
    return "\n".join([entry.get("position", ""), entry.get("summary", ""), *entry.get("highlights", [])])


def corpus(data: dict) -> str:
    """All candidate-authored text: the universe of claims tailoring may draw from."""
    parts = [data["basics"].get("label", ""), data["basics"].get("summary", "")]
    for w in data.get("work", []):
        parts.append(work_text(w))
    for p in data.get("projects", []):
        parts += [p.get("name", ""), p.get("description", ""), *p.get("highlights", []), *p.get("keywords", [])]
    for s in data.get("skills", []):
        parts += [s.get("name", ""), *s.get("keywords", [])]
    for e in data.get("education", []):
        parts += [e.get("institution", ""), e.get("area", ""), e.get("studyType", "")]
    for c in data.get("certificates", []):
        parts.append(c.get("name", ""))
    return "\n".join(p for p in parts if p)


def candidate_keywords(data: dict) -> set[str]:
    return set(keywords.extract(corpus(data)))


def find_mutations(master: dict, tailored: dict) -> list[str]:
    """Return dotted paths where `tailored` differs from `master` outside MUTABLE_PATHS."""
    problems: list[str] = []

    def allowed(path: tuple) -> bool:
        for pat in MUTABLE_PATHS:
            if len(path) >= len(pat) and all(p == "*" or p == q for p, q in zip(pat, path)):
                return True
        return False

    def walk(a, b, path: tuple):
        if allowed(tuple("*" if isinstance(x, int) else x for x in path)) or allowed(path):
            return
        if isinstance(a, dict) and isinstance(b, dict):
            for k in set(a) | set(b):
                walk(a.get(k), b.get(k), path + (k,))
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                problems.append(".".join(map(str, path)) + " (length changed)")
                return
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, path + (i,))
        elif a != b:
            problems.append(".".join(map(str, path)))

    walk(master, tailored, ())
    return problems


def clone(data: dict) -> dict:
    return copy.deepcopy(data)
