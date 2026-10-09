"""Deterministic skill/keyword extraction used for scoring and for the
anti-fabrication guard. Deliberately vocabulary-based so results are
reproducible and testable without an LLM."""
from __future__ import annotations

import re

# canonical name -> extra aliases (all matched case-insensitively on word boundaries)
VOCAB: dict[str, list[str]] = {
    # languages
    "Python": [], "Java": [], "JavaScript": ["JS"], "TypeScript": ["TS"], "Go": ["Golang"],
    "Rust": [], "C++": ["cpp"], "C#": ["csharp", ".NET", "dotnet"], "Ruby": [], "PHP": [],
    "Scala": [], "Kotlin": [], "Swift": [], "Elixir": [], "Haskell": [], "Clojure": [],
    "SQL": [], "Bash": ["shell scripting"], "R": [],
    # frontend
    "React": ["React.js", "ReactJS"], "Next.js": ["NextJS"], "Vue": ["Vue.js"], "Angular": [],
    "Svelte": [], "HTML": [], "CSS": [], "Tailwind": ["TailwindCSS"], "Redux": [], "GraphQL": [],
    # backend frameworks
    "Node.js": ["NodeJS", "Node"], "Django": [], "Flask": [], "FastAPI": [], "Spring": ["Spring Boot"],
    "Rails": ["Ruby on Rails"], "Express": ["Express.js"], "gRPC": [], "REST": ["RESTful"],
    # data
    "PostgreSQL": ["Postgres"], "MySQL": [], "MongoDB": ["Mongo"], "Redis": [], "Elasticsearch": [],
    "Cassandra": [], "DynamoDB": [], "Snowflake": [], "BigQuery": [], "Redshift": [],
    "Kafka": [], "RabbitMQ": [], "Spark": ["PySpark"], "Airflow": [], "dbt": [], "Flink": [],
    "Hadoop": [], "ETL": [], "Data Warehousing": ["data warehouse"],
    # cloud / infra
    "AWS": ["Amazon Web Services"], "GCP": ["Google Cloud"], "Azure": [], "Kubernetes": ["k8s"],
    "Docker": [], "Terraform": [], "Ansible": [], "Helm": [], "Linux": [], "CI/CD": ["CICD"],
    "GitHub Actions": [], "Jenkins": [], "Prometheus": [], "Grafana": [], "Datadog": [],
    "OpenTelemetry": [], "Serverless": ["Lambda"], "Microservices": ["microservice"],
    "Distributed Systems": ["distributed system"], "Observability": [], "SRE": ["site reliability"],
    # ml / ai
    "Machine Learning": ["ML"], "Deep Learning": [], "PyTorch": [], "TensorFlow": [],
    "scikit-learn": ["sklearn"], "NLP": ["natural language processing"], "LLM": ["LLMs", "large language model"],
    "Computer Vision": [], "MLOps": [], "Pandas": [], "NumPy": [],
    # practices
    "Agile": ["Scrum"], "TDD": ["test-driven"], "System Design": [], "Security": [],
    "Mentoring": ["mentorship", "mentored"], "Leadership": ["led a team", "team lead"],
    "API Design": [], "Performance Optimization": ["performance tuning"],
    "iOS": [], "Android": [], "React Native": [], "Flutter": [],
    "Backend": ["back-end", "backend engineering"], "Frontend": ["front-end"], "Full Stack": ["full-stack", "fullstack"],
    "Temporal": [], "Developer Experience": ["DevEx"], "AI Agents": ["agentic", "LLM agents"],
    # hardware / embedded
    "RTL": [], "Verilog": [], "SystemVerilog": [], "VHDL": [], "UVM": [], "FPGA": [], "ASIC": [],
    "CUDA": [], "GPU": ["GPUs"], "Embedded Systems": ["embedded software", "embedded linux", "embedded firmware"],
    "Firmware": [], "RTOS": [],
    "Perl": [], "Tcl": [], "MATLAB": [],
}

# Very short / ambiguous tokens that need case-sensitive matching to avoid noise.
_CASE_SENSITIVE = {"Go", "R", "Node", "ML", "JS", "TS", "Swift", "Spring", "Express", "Rust", "Lambda"}


def _compile() -> list[tuple[str, re.Pattern]]:
    patterns = []
    for canon, aliases in VOCAB.items():
        for term in [canon, *aliases]:
            flags = 0 if term in _CASE_SENSITIVE else re.IGNORECASE
            pat = re.compile(r"(?<![\w+#.])" + re.escape(term) + r"(?![\w+#])", flags)
            patterns.append((canon, pat))
    return patterns


_PATTERNS = _compile()


def extract(text: str) -> list[str]:
    """Canonical skills mentioned in `text`, in order of first appearance."""
    if not text:
        return []
    hits: dict[str, int] = {}
    for canon, pat in _PATTERNS:
        m = pat.search(text)
        if m and (canon not in hits or m.start() < hits[canon]):
            hits[canon] = m.start()
    return sorted(hits, key=hits.get)


MIN_SCORING_KEYWORDS = 4


def match_score(job_keywords: list[str], candidate_keywords: set[str]) -> float:
    """Share of the posting's skills the candidate has. The denominator has a floor
    so a posting that only mentions one known skill can't score 100%."""
    if not job_keywords:
        return 0.0
    have = sum(1 for k in job_keywords if k in candidate_keywords)
    return round(have / max(len(job_keywords), MIN_SCORING_KEYWORDS), 3)


NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*(?:\s*%|(?:x|k|m|b|ms|s)(?![a-z])|\+)?", re.IGNORECASE)


def numbers(text: str) -> set[str]:
    return {re.sub(r"\s+", "", m.group(0)).lower().rstrip("+") for m in NUMBER_RE.finditer(text or "")}
