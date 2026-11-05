import os
from functools import lru_cache

import sqlalchemy as sa

from it_support_ticket_triage.config import settings as config

metadata = sa.MetaData()

teams = sa.Table(
    "teams", metadata,
    sa.Column("category", sa.String(30), primary_key=True),
    sa.Column("team_name", sa.String(100), nullable=False),
    sa.Column("team_email", sa.String(150)),
)

faq_articles = sa.Table(
    "faq_articles", metadata,
    sa.Column("kb_id", sa.String(10), primary_key=True),
    sa.Column("title", sa.String(200), nullable=False),
    sa.Column("category", sa.String(30), nullable=False),
    sa.Column("keywords", sa.Text, nullable=False),     # comma-separated
    sa.Column("body", sa.Text, nullable=False),
)

tickets = sa.Table(
    "tickets", metadata,
    sa.Column("ticket_id", sa.String(12), primary_key=True),
    sa.Column("subject", sa.String(200), nullable=False),
    sa.Column("description", sa.Text, nullable=False),
    sa.Column("category", sa.String(30), nullable=False),
    sa.Column("priority", sa.String(10), nullable=False),
    sa.Column("status", sa.String(20), nullable=False),   # open / in_progress / resolved
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("resolution_hours", sa.Float),
    sa.Column("assigned_team", sa.String(100)),
)

triage_log = sa.Table(
    "triage_log", metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("subject", sa.String(200)),
    sa.Column("description", sa.Text),
    sa.Column("result", sa.Text),                          # full JSON result
)


@lru_cache(maxsize=1)
def get_engine() -> sa.Engine:
    if config.DB_BACKEND == "sqlite":
        return sa.create_engine(config.SQLITE_URL)

    from google.cloud.sql.connector import Connector   # imported lazily: not needed in sqlite mode

    connector = Connector(refresh_strategy="lazy")      # lazy refresh suits Cloud Run's CPU throttling

    def _connect():
        return connector.connect(
            os.environ["INSTANCE_CONNECTION_NAME"], "pg8000",
            user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], db=os.environ["DB_NAME"],
        )

    return sa.create_engine("postgresql+pg8000://", creator=_connect, pool_size=2, max_overflow=2,
                            pool_pre_ping=True)
