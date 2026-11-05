from dotenv import load_dotenv
load_dotenv()

import logging
from pathlib import Path

import sqlalchemy as sa
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from it_support_ticket_triage.backend.db import get_engine
from it_support_ticket_triage.pipeline.pipeline import triage

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent.parent
app = FastAPI(title="IT Support Ticket Triage POC")


class TicketRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=4000)


@app.post("/triage")
def triage_ticket(req: TicketRequest):
    try:
        return triage(get_engine(), req.subject.strip(), req.description.strip())
    except sa.exc.SQLAlchemyError:
        log.exception("Database error")
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(PACKAGE_DIR / "ui" / "index.html")
