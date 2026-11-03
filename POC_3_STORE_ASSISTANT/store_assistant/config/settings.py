import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UI_DIR = Path(__file__).resolve().parents[1] / "ui"
DATA_DIR = PROJECT_ROOT / "data"
load_dotenv(PROJECT_ROOT / ".env")

GOOGLE_CLOUD_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
FIRESTORE_DB = os.getenv("FIRESTORE_DB", "store-assistant-db")
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "U001")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
