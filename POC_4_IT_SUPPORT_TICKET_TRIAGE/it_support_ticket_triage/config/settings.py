import os

USE_LLM = os.getenv("USE_LLM", "true").lower() == "true"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
DB_BACKEND = os.getenv("DB_BACKEND", "cloudsql")          # "cloudsql" or "sqlite"
SQLITE_URL = os.getenv("SQLITE_URL", "sqlite:///local.db")

# Routing thresholds: POC defaults, tune against real data.
MIN_CATEGORY_CONFIDENCE = 0.60       # below this -> human triage
HIGH_PRIORITY_MIN_CONFIDENCE = 0.80  # urgent tickets need a more confident category
KB_MIN_SCORE = 0.33                  # 1 keyword hit  -> article is suggested
KB_STRONG_SCORE = 0.66               # 2+ keyword hits -> article counts as a strong match

# Target response times per priority. Assumed POC values, not an official SLA.
SLA_HOURS = {"high": 4, "medium": 24, "low": 72}
