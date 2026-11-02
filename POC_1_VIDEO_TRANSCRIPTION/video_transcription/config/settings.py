from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRAINING_ZIP = PROJECT_ROOT / "data" / "input" / "training.zip"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"

WHISPER_MODEL = "small"
LANGUAGE_CODE = "en-US"
