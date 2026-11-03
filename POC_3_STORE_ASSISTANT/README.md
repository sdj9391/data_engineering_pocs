# POC 3: Store Assistant

A consumer-electronics store chatbot built with Google ADK, Gemini on Vertex AI,
FastAPI, and Firestore. The root agent delegates product, promotion, and order
questions to three specialized agents. Products and prices come from Firestore;
order tools filter results by the selected demo user.

## Project structure

```text
POC_3_STORE_ASSISTANT/
├── .env                         # Local configuration (not committed)
├── .venv/                       # Python 3.12+ environment (not committed)
├── pyproject.toml               # Dependencies and package configuration
├── Dockerfile
├── .dockerignore
├── .gcloudignore
├── README.md
├── data/                        # Preserved synthetic JSON data
│   ├── products.json
│   ├── users.json
│   ├── promotions.json
│   └── orders.json
├── scripts/
│   ├── generate_data.py         # Optional: refresh synthetic data dates
│   └── seed_firestore.py        # Load local JSON into Firestore
└── store_assistant/
    ├── __init__.py
    ├── main.py                  # Uvicorn application entry point
    ├── agent.py                 # ADK discovery entry point
    ├── backend/
    │   ├── app.py               # Chat API, sessions, health, and UI route
    │   ├── agents.py            # Root agent and three sub-agents
    │   └── tools.py             # Firestore-backed tools
    ├── config/
    │   └── settings.py          # Shared paths and configuration
    └── ui/
        └── index.html
```

The local package is `store_assistant`; the Cloud Run service is `store-assistant`
because cloud service names cannot contain underscores. Backend/config directories
use namespace packages, matching the other POCs. `agent.py` is required for ADK to
discover `root_agent`; `main.py` exposes the FastAPI app to Uvicorn.

Seed Firestore directly from local JSON files using `scripts/seed_firestore.py`.

## Step 1. Project, billing, and APIs

Select project `brilliant-fire-2212` in Google Cloud Console and ensure billing is
enabled. Gemini, Firestore, Cloud Run, builds, and image storage can incur charges.

Install the Google Cloud CLI and Python 3.12 if needed:

```bash
brew install --cask google-cloud-sdk
brew install python@3.12
gcloud auth login
gcloud config set project brilliant-fire-2212
gcloud services enable firestore.googleapis.com aiplatform.googleapis.com \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  --project brilliant-fire-2212
```

Use your own project ID throughout if deploying elsewhere.

## Step 2. Firestore database

The database is **`store-assistant-db`**, not `(default)`. If it already exists,
skip creation. Otherwise create a **Firestore Native** database from the Firestore
databases page, or run:

```bash
gcloud firestore databases create --database store-assistant-db \
  --location us-central1 --type firestore-native --project brilliant-fire-2212
```

Choose the database location carefully; it cannot be changed later. The existing
database can remain in its current location. Server access uses IAM rather than
Firebase client security rules.

## Step 3. Local environment and credentials

From the repository root:

```bash
cd POC_3_STORE_ASSISTANT
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
gcloud auth application-default login
gcloud auth application-default set-quota-project brilliant-fire-2212
```

If your terminal still has the former nested environment activated, run
`deactivate` before activating the new project-level `.venv`.

Create or update `.env` in **`POC_3_STORE_ASSISTANT/`**, outside the package:

```dotenv
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=brilliant-fire-2212
GOOGLE_CLOUD_LOCATION=global
GEMINI_MODEL=gemini-3.8-flash
FIRESTORE_DB=store-assistant-db
DEFAULT_USER_ID=U001
```

This model was successfully tested using `global`; a regional endpoint returned
404. Gemini's endpoint is independent of the Cloud Run and Firestore regions.
Use a supported model/endpoint for your project, and consider residency requirements
before using global processing. Existing shell variables take precedence over `.env`.

Your local Google account needs Firestore write access for seeding (for example,
**Cloud Datastore User**) and **Vertex AI User** for model calls. Python 3.9 is
unsupported for this POC. Dependencies, including `python-multipart`, are declared
in `pyproject.toml`.

## Step 4. Seed Firestore from local data

From `POC_3_STORE_ASSISTANT/` with `.venv` activated:

```bash
python scripts/seed_firestore.py
```

The script loads `data/*.json` into the database configured by `FIRESTORE_DB`,
converts ISO date strings to timestamps, and writes documents by ID in batches.
Re-running overwrites matching document IDs; it does not remove other documents.

Optional: refresh the synthetic fixture dates before seeding:

```bash
python scripts/generate_data.py
python scripts/seed_firestore.py
```

Generating data replaces the local JSON files; it is not required to run the app.
Keep all input JSON in `data/`, and do not load real customer data into this POC.

Verify in **Firestore → store-assistant-db → Data**: `products` (12), `users` (4),
`promotions` (6), and `orders` (7). Date fields should be timestamps, not strings.

## Step 5. Run and test locally

In each new terminal, from `POC_3_STORE_ASSISTANT/`:

```bash
source .venv/bin/activate
uvicorn store_assistant.main:app --reload --port 8080
```

Open http://localhost:8080 for the UI, http://localhost:8080/docs for API docs,
or http://localhost:8080/health for the health check.

For the ADK development UI instead:

```bash
adk web .
```

Open http://localhost:8000 and select **store_assistant**. Run ADK from the POC
root, not inside `store_assistant/`. `DEFAULT_USER_ID` supplies the demo user
for ADK tools without user state. Stop either server with **Ctrl+C** and restart
after config/model changes. Stop any existing listener before reusing its port.

## Step 6. Deploy the full app to Cloud Run

Run from **`POC_3_STORE_ASSISTANT/`**, where the Dockerfile is located, after
installing dependencies and configuring APIs. Your deploying account needs Cloud
Run/build permissions and permission to use the runtime service account.

Create the runtime service account **only if it does not already exist**:

```bash
gcloud iam service-accounts create store-assistant-sa --project brilliant-fire-2212
```

Grant it read access to Firestore and permission to call Vertex AI:

```bash
gcloud projects add-iam-policy-binding brilliant-fire-2212 \
  --member="serviceAccount:store-assistant-sa@brilliant-fire-2212.iam.gserviceaccount.com" \
  --role="roles/datastore.viewer"
gcloud projects add-iam-policy-binding brilliant-fire-2212 \
  --member="serviceAccount:store-assistant-sa@brilliant-fire-2212.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

Deploy (also use this command to redeploy after code changes):

```bash
gcloud run deploy store-assistant \
  --project brilliant-fire-2212 \
  --source . --region us-central1 \
  --service-account store-assistant-sa@brilliant-fire-2212.iam.gserviceaccount.com \
  --max-instances 1 --no-allow-unauthenticated \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=brilliant-fire-2212,GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL=gemini-3.8-flash,FIRESTORE_DB=store-assistant-db"
```

Answer **Y** if asked to create the `cloud-run-source-deploy` Artifact Registry
repository. Existing-service-account conflicts mean skip creation, not deployment.
Cloud Run requires a regional location: `--region global` is invalid.

The ignore files exclude local environments, `.env`, ADK state, and fixture data
from deployment. Cloud Run uses its service account, not your local credentials.
Its configuration is supplied explicitly; `.env` is not included in the image.

Keep the service private: the UI's demo-user selector is **not authentication**.
To test through an authenticated local proxy:

```bash
gcloud run services proxy store-assistant --region us-central1 \
  --project brilliant-fire-2212 --port 8080
```

Keep the proxy running and open http://localhost:8080. Your account needs Cloud
Run invocation permission. Opening the deployed URL directly may return 403.
Cloud Run logs and revisions are under **Cloud Run → store-assistant**.

## Step 7. Demo checks

| Demo user | Prompt | Expected |
|---|---|---|
| Any | Show noise cancelling headphones under $200 | Matching Firestore products and prices |
| Any | Is the NovaBook Pro 16 available? | Out of stock |
| Aisha | Can I use GOLD15 on a $300 order? | Eligible, if fixture dates are current |
| Omar | Can I use GOLD15 on a $300 order? | Ineligible tier |
| Sam | Can I use WELCOME10? | Eligible, if fixture dates are current |
| Aisha | Can I use AUDIO20? | Already used |
| Any | Can I use BLACKFRI25? | Expired |
| Aisha | Where is order O1002? | Shipped, DHL tracking DHL100002 |
| Omar | What is the status of O1002? | Not found for that user |
| Lina | What happened to O1005? | Cancelled; refund issued |

## Limits and cleanup

- Demo identities are supplied by the client. Production must derive user IDs
  from verified server-side authentication.
- Sessions are in memory. One instance limits scaling but sessions are still lost
  on container restarts; production needs persistent sessions.
- Product search is keyword matching over a small catalog, not semantic search.
- ADK/model behavior can vary by version; use the same working environment for
  development and validate upgrades before deployment.

To remove the Cloud Run service when no longer needed:

```bash
gcloud run services delete store-assistant --region us-central1 \
  --project brilliant-fire-2212
```

Review Artifact Registry images and other retained resources for ongoing costs.
Delete `store-assistant-db` only if its data is no longer needed. Do not delete
`brilliant-fire-2212` as POC cleanup: the other POCs use this project too.
