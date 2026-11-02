# POC 1: Video Transcription

Create audio files and transcripts from videos in a ZIP archive. Audio extraction
and speech recognition run locally using ffmpeg and faster-whisper. No cloud
account or credentials are required, and audio is not uploaded.

## Setup

Use Python 3.9 or later and install ffmpeg (on macOS: `brew install ffmpeg`).
From the repository root:

```sh
cd POC_1_VIDEO_TRANSCRIPTION
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Run

From `POC_1_VIDEO_TRANSCRIPTION`, place your videos in
`data/input/training.zip`, then run:

```sh
python main.py
```

Results are saved under `data/output/`, preserving the archive's video folders.
Each video produces a full WAV, five-minute WAV chunks, and TXT/JSON transcripts
for both the chunks and the complete video.

Edit `transcription_poc/config.py` to change the input/output paths, Whisper model,
or language. The default model is `small`. The first run downloads the model
weights and requires internet access; subsequent runs can use the cached model
offline. You can also set `WHISPER_MODEL` to a local faster-whisper model directory.

In the IDE, run this directory's `main.py`, not `transcription_poc/pipeline.py`.
If reusing the repository-root virtual environment, refresh its editable install
from this directory with `../.venv/bin/python -m pip install -e .`.
