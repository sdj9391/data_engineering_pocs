"""Priority agent: deterministic urgency rules, plus average resolution time of similar past tickets."""
import re

import sqlalchemy as sa

from it_support_ticket_triage.backend.db import tickets
from it_support_ticket_triage.backend.textutil import normalize

HIGH_PATTERNS = [
    ("outage", r"\boutage"),
    ("service down", r"\b(?:is|are|was|went|gone|completely|totally|still)\s+down\b"),
    ("cannot login", r"\b(?:can'?t|cannot|can not|unable to)\s+(?:log ?in|sign ?in)\b"),
    ("locked out", r"\blocked out\b"),
    ("data loss", r"\bdata loss\b|\blost (?:all )?(?:my |our )?(?:data|files)\b"),
    ("security incident", r"\bransomware\b|\bbreach\b|\bhacked\b"),
    ("many users affected", r"\b(?:all users|everyone|everybody|entire office|whole office|entire team|whole team)\b"),
    ("production impact", r"\bproduction\b"),
]

MEDIUM_PATTERNS = [
    ("slow", r"\bslow"),
    ("intermittent", r"\bintermittent"),
    ("error", r"\berror"),
    ("crash", r"\bcrash"),
    ("freezing", r"\bfreez|\bfrozen"),
    ("not working", r"\bnot working\b|\bstopped working\b"),
    ("failing", r"\bfail"),
    ("dropping", r"\bkeeps? (?:dropping|disconnecting)"),
]

CATEGORY_DEFAULT = {"network": "medium", "access": "medium", "hardware": "low", "software": "low", "other": "low"}


def _matches(patterns, text):
    return [label for label, rx in patterns if re.search(rx, text)]


def _avg_resolution(engine, category: str, priority: str):
    """Average hours to resolve similar resolved tickets: same category+priority, else same category."""
    filters = ((("same category and priority"), {"category": category, "priority": priority}),
               (("same category"), {"category": category}))
    with engine.connect() as conn:
        for basis, cols in filters:
            stmt = sa.select(sa.func.avg(tickets.c.resolution_hours), sa.func.count(tickets.c.resolution_hours)).where(
                tickets.c.status == "resolved", *[tickets.c[k] == v for k, v in cols.items()])
            avg, n = conn.execute(stmt).one()
            if n:
                return round(float(avg), 1), n, basis
    return None, 0, "no similar resolved tickets"


def assess_priority(engine, subject: str, description: str, category: str) -> dict:
    text = normalize(f"{subject} {description}")
    high, medium = _matches(HIGH_PATTERNS, text), _matches(MEDIUM_PATTERNS, text)
    if high:
        priority, reasons = "high", [f"urgent keyword: {h}" for h in high]
    elif medium:
        priority, reasons = "medium", [f"keyword: {m}" for m in medium]
    else:
        priority = CATEGORY_DEFAULT.get(category, "low")
        reasons = [f"category default for '{category}'"]
    avg_hours, n, basis = _avg_resolution(engine, category, priority)
    return {"priority": priority, "reasons": reasons, "avg_resolution_hours": avg_hours,
            "similar_resolved_tickets": n, "resolution_basis": basis}
