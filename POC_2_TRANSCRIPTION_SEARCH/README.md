# POC 2: Transcription Search

Search indexed training transcripts with Google Cloud Discovery Engine through
a small FastAPI application.

## Goals
1. Create a Vertex AI Search app in GCP.
2. Create a data store holding the transcriptions.
3. Test queries in the app's **Preview** tab.
4. Install the Python SDK on a Mac.
5. Build a FastAPI endpoint connected to the app.
6. Build an HTML UI (search box + results) that consumes the endpoint.


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

## GCP setup

1. Project and API
- Go to console.cloud.google.com and select (or create) a project. Billing must be enabled.
- Enable the Discovery Engine API (APIs & Services → Library). Also enable the Vertex AI Search / AI Applications API if the console prompts you.

2. Upload transcripts to Cloud Storage
- Go to Cloud Storage → Create bucket (for example training-transcripts-<id>) and pick a region.
- Upload your transcripts. .txt, .pdf, .html and .docx all work. One file per video is ideal, and the file name should be the video title because it shows up in results.

3. Create the data store 
- Open AI Applications (formerly Agent Builder) → Data Stores → Create data store.
- Choose the source Cloud Storage.
- Choose Unstructured documents and select your bucket or folder.
- Leave it as a document import with no metadata. Use JSONL with metadata instead if you want fields such as video URL, speaker or date.
- Set the location to global (simplest) and name the store. Click Create.
- Wait for the import to finish. Check Data → Documents for the status, which can take several minutes.

4. Create the Search app
- Go to Apps → Create app → Custom search (general).
- Turn on Enterprise edition features and Advanced LLM features. These give you snippets and extractive answers.
- Name the app, then attach the data store you created.
- Note the App ID (the engine ID) from the app list.

5. Test in Preview
- Open the app and go to the Preview tab.
- Try queries such as “how do I reset the password”, “what is covered in the onboarding session” or “who explained deployment”.
- If results are empty, the import probably hasn’t finished indexing.

## Setup and run Local Development Server

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
