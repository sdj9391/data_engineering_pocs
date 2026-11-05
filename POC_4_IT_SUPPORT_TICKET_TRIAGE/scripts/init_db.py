"""Creates the tables and loads data/*.csv into the database (Cloud SQL, or SQLite with DB_BACKEND=sqlite).
Run from the project root:  python scripts/init_db.py          (add --reset to drop and recreate tables)
"""
import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from it_support_ticket_triage.backend.db import faq_articles, get_engine, metadata, teams, tickets  # noqa: E402

DATA = ROOT / "data"


def rows(name):
    with open(DATA / name, newline="") as f:
        return list(csv.DictReader(f))


engine = get_engine()
if "--reset" in sys.argv:
    metadata.drop_all(engine)
metadata.create_all(engine)

ticket_rows = [{**r,
                "submitted_at": datetime.fromisoformat(r["submitted_at"].replace("Z", "+00:00")),
                "resolution_hours": float(r["resolution_hours"]) if r["resolution_hours"] else None}
               for r in rows("tickets.csv")]

with engine.begin() as conn:               # one transaction: all or nothing
    for table in (tickets, faq_articles, teams):
        conn.execute(table.delete())       # makes re-running safe
    conn.execute(teams.insert(), rows("teams.csv"))
    conn.execute(faq_articles.insert(), rows("faq_articles.csv"))
    conn.execute(tickets.insert(), ticket_rows)

print(f"Loaded: {len(rows('teams.csv'))} teams, {len(rows('faq_articles.csv'))} FAQ articles, {len(ticket_rows)} tickets")
