"""Knowledge lookup agent: keyword match of the ticket against FAQ articles.

Score = distinct article keywords found in the ticket / 3, capped at 1.0.
(Stretch: replace this with Vertex AI Search or Vector Search for semantic matching.)
"""
import sqlalchemy as sa

from it_support_ticket_triage.config import settings as config
from it_support_ticket_triage.backend.db import faq_articles
from it_support_ticket_triage.backend.textutil import has_term, normalize


def find_article(engine, subject: str, description: str, key_phrases: list[str]) -> dict | None:
    text = normalize(" ".join([subject, description, *key_phrases]))
    best = None
    with engine.connect() as conn:
        for row in conn.execute(sa.select(faq_articles)).mappings():
            keywords = [k.strip() for k in row["keywords"].split(",") if k.strip()]
            hits = [k for k in keywords if has_term(text, normalize(k))]
            score = min(1.0, len(hits) / 3)
            if score >= config.KB_MIN_SCORE and (best is None or score > best["score"]):
                best = {"kb_id": row["kb_id"], "title": row["title"], "category": row["category"],
                        "score": round(score, 2), "matched_keywords": hits, "body": row["body"]}
    return best
