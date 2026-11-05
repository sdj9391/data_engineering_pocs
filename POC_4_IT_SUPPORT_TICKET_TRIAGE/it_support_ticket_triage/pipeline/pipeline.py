import json
import logging
from datetime import datetime, timezone

import sqlalchemy as sa

from it_support_ticket_triage.backend import routing
from it_support_ticket_triage.backend.db import teams, triage_log
from it_support_ticket_triage.pipeline import intake_agent, knowledge_agent, priority_agent

log = logging.getLogger(__name__)


def _team_for(engine, category: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(sa.select(teams).where(teams.c.category == category)).mappings().first()
    return dict(row) if row else None


def triage(engine, subject: str, description: str) -> dict:
    intake_result = intake_agent.analyze(subject, description)
    priority_result = priority_agent.assess_priority(engine, subject, description, intake_result["category"])
    kb = knowledge_agent.find_article(engine, subject, description, intake_result["key_phrases"])
    team = _team_for(engine, intake_result["category"])
    decision = routing.decide(intake_result, priority_result, kb, team)

    result = {"intake": intake_result, "priority": priority_result, "knowledge_base": kb, "routing": decision}
    try:   # audit trail; a logging failure must not fail the triage
        with engine.begin() as conn:
            conn.execute(triage_log.insert().values(
                created_at=datetime.now(timezone.utc), subject=subject, description=description,
                result=json.dumps(result)))
    except sa.exc.SQLAlchemyError:
        log.exception("Could not write triage_log")
    return result
