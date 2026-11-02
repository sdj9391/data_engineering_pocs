# POC 2: Transcription Search

Search indexed training transcripts with Google Cloud Discovery Engine through
a small FastAPI application.

## Project structure

```text
POC_2_TRANSCRIPTION_SEARCH/
├── .env                         # Local Google Cloud app settings (not committed)
├── .venv/                       # Local Python environment (not committed)
├── pyproject.toml               # Project metadata and dependencies
└── transcript_search/
    ├── main.py                  # Application entry point
    ├── backend/
    │   └── app.py               # FastAPI routes and Discovery Engine search
    └── ui/
        └── index.html           # Search interface
```

## Setup and run

From the repository root, set up the environment, authenticate with Google
Cloud, and start the development server:

```bash
cd POC_2_TRANSCRIPTION_SEARCH
source .venv/bin/activate
uvicorn transcript_search.main:app --reload
```

Open <http://localhost:8000>. The app reads `PROJECT_ID`, `LOCATION`, and
`APP_ID` from `.env`. The Google account used for Application Default
Credentials must have access to the Discovery Engine app.
