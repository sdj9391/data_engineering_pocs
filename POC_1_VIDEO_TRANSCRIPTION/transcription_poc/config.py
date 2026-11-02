# Central configuration for input files, output files, and local transcription.
from pathlib import Path

# Build paths from the project location instead of the current terminal folder.
ROOT = Path(__file__).resolve().parent.parent
TRAINING_ZIP = ROOT / "data" / "input" / "training.zip"
OUTPUT_DIR = ROOT / "data" / "output"

WHISPER_MODEL = "small"
LANGUAGE_CODE = "en-US"
