"""Load data/*.json into the configured Firestore database from your Mac.
Run from POC_3_STORE_ASSISTANT: python scripts/seed_firestore.py
Dates (ISO strings in the JSON) are converted to Firestore Timestamps.
"""
import json
from datetime import datetime
from google.cloud import firestore

from store_assistant.config import settings

DATA = settings.DATA_DIR
ID_FIELD = {"products": "id", "users": "user_id", "promotions": "code", "orders": "order_id"}
DATE_FIELDS = {"signup_date", "valid_from", "valid_to", "order_date", "estimated_delivery"}

def fix_dates(doc: dict) -> dict:
    for k in DATE_FIELDS & doc.keys():
        if doc[k]:
            doc[k] = datetime.fromisoformat(doc[k].replace("Z", "+00:00"))
    return doc


def seed():
    db = firestore.Client(
        project=settings.GOOGLE_CLOUD_PROJECT,
        database=settings.FIRESTORE_DB,
    )
    for coll, key in ID_FIELD.items():
        docs = json.loads((DATA / f"{coll}.json").read_text(encoding="utf-8"))
        batch = db.batch()
        for i, doc in enumerate(docs, 1):
            batch.set(db.collection(coll).document(str(doc[key])), fix_dates(doc))
            if i % 400 == 0:
                batch.commit()
                batch = db.batch()
        if len(docs) % 400:
            batch.commit()
        print(f"{coll}: {len(docs)} docs loaded")


if __name__ == "__main__":
    seed()
