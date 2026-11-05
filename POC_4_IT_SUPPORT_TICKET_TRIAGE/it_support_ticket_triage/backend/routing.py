"""Routing decision: deterministic rules only (no LLM call).

Any triggered rule sends the ticket to human triage; otherwise it is assigned to the category's team.
"""
from it_support_ticket_triage.config import settings as config


def decide(intake: dict, priority: dict, kb: dict | None, team: dict | None) -> dict:
    category, confidence, prio = intake["category"], intake["category_confidence"], priority["priority"]
    flags = []

    if confidence < config.MIN_CATEGORY_CONFIDENCE:
        flags.append(f"low_category_confidence ({confidence:.2f} < {config.MIN_CATEGORY_CONFIDENCE})")
    if team is None:
        flags.append(f"no_team_for_category ('{category}')")
    if kb and kb["score"] >= config.KB_STRONG_SCORE and kb["category"] != category:
        flags.append(f"category_kb_conflict (intake '{category}' vs article '{kb['category']}')")
    if prio == "high" and confidence < config.HIGH_PRIORITY_MIN_CONFIDENCE:
        flags.append(f"high_priority_needs_confident_category ({confidence:.2f} < {config.HIGH_PRIORITY_MIN_CONFIDENCE})")

    base = {"priority": prio, "urgent": prio == "high", "target_response_hours": config.SLA_HOURS[prio]}
    if flags:
        return {**base, "decision": "NEEDS_HUMAN_TRIAGE", "team": None, "team_email": None, "reasons": flags}

    reasons = [f"category '{category}' with confidence {confidence:.2f}"]
    if kb and kb["category"] == category:
        reasons.append(f"KB article {kb['kb_id']} agrees (score {kb['score']})")
    return {**base, "decision": "ASSIGN_TEAM", "team": team["team_name"], "team_email": team["team_email"],
            "reasons": reasons}
