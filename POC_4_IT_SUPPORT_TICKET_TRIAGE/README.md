# IT Support Ticket Triage & Routing Assistant (POC)

Submit an IT ticket subject and description to get a suggested **category**, **priority**, **knowledge-base article**, and **routing decision**. Gemini on Vertex AI classifies tickets. Priority, knowledge lookup, and team routing use deterministic rules. Low-confidence or conflicting tickets are sent to `NEEDS_HUMAN_TRIAGE`.

This guide uses the **Google Cloud Console** for setup, deployment, running, and cleanup. You do not need a local Python environment or terminal commands. You will need the project source in a GitHub repository connected to Cloud Build.

## Project layout

```text
POC_4_IT_SUPPORT_TICKET_TRIAGE/
├── Dockerfile
├── pyproject.toml
├── it_support_ticket_triage/
│   ├── main.py                 Uvicorn entry point
│   ├── backend/                FastAPI app, database, routing and text utilities
│   ├── config/settings.py      thresholds and feature flags
│   ├── pipeline/               triage flow and intake/knowledge/priority agents
│   └── ui/index.html           ticket submission UI
└── scripts/
    ├── generate_data.py        creates synthetic CSVs during image build
    └── init_db.py              creates tables and loads the synthetic data
```

`data/` is Git-ignored. Cloud Build sends the tracked source to the builder, and the Dockerfile generates synthetic database inputs inside the image. `data/sample_tickets.json` is only a local manual reference; the application does not use or deploy it.

## Names used in this guide

Use these exact names so the later steps match. If you choose different names, change them everywhere they appear.

| Resource | Name |
|---|---|
| Service account | `it-ticket-triage-run-sa` (email: `it-ticket-triage-run-sa@PROJECT_ID.iam.gserviceaccount.com`) |
| Secret | `db-password` |
| Cloud SQL instance | `it-ticket-triage-pg` (connection name: `PROJECT_ID:us-central1:it-ticket-triage-pg`) |
| Database / DB user | `it-ticket-triage` / `it_ticket_triage_app` |
| Artifact Registry repository | `it-ticket-triage-poc-images` |
| Cloud Run job / service | `it-ticket-triage-db-init` / `it-ticket-triage-poc` |

## Before you start

**Cloud SQL incurs charges while the instance exists, including when idle.** Cloud Run scales down when idle, but Cloud SQL and stored container images may continue to cost money. A budget alert only notifies you; it does not stop spending. Use a dedicated POC project, follow the cleanup section as soon as you finish, and delete the whole project if it contains no resources you need to keep.

Use synthetic data only. The Cloud Run service can be kept private, or you can temporarily allow public access to use the browser UI without a proxy. The public option exposes the ticket API and can be abused to incur Gemini costs; do not use it with real tickets, and switch it off after trying the app.

## 1. Create a Google Cloud project

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and create a **dedicated** project, or select a project that contains no resources you need to preserve.
2. Link billing to the project.
3. Open **Billing → Budgets & alerts** and create a budget with email alerts (for example 50%, 90%, and 100%). Alerts do not cap usage or automatically shut down resources.
4. Select the project using the project picker at the top of the Console. Use `us-central1` consistently for the resources in this guide.
5. Open **APIs & Services → Library** and enable:
   - Cloud SQL Admin API
   - Vertex AI API
   - Cloud Run Admin API
   - Cloud Build API
   - Artifact Registry API
   - Secret Manager API

## 2. Create the runtime service account

1. Open **IAM & Admin → Service Accounts → Create service account**.
2. Name it `it-ticket-triage-run-sa`; create it without granting any roles on the creation screen. Click **Done**.
3. Confirm it exists in **IAM & Admin → Service Accounts** (check that the project picker shows your POC project) and copy its email: `it-ticket-triage-run-sa@PROJECT_ID.iam.gserviceaccount.com`.
4. Grant it project roles:
   1. Open **IAM & Admin → IAM → Grant access**.
   2. In **New principals**, paste the service account email.
   3. Under **Role**, select **Cloud SQL Client** (lets the app and initialization job connect through the Cloud SQL connector). Click **Add another role** and select **Agent Platform User** (lets the app call Gemini).
   4. Click **Save**.

   **Note:** a new service account does **not** appear on the **IAM** page until it has been granted at least one role. If you look for it there before this step, it will not be listed. Use **Service Accounts** to find it, and **Grant access** to give it roles.
5. In Step 3 you will also grant it **Secret Manager Secret Accessor** on the `db-password` secret only. Do not grant the service account project Owner.

## 3. Create and save the database password secret

1. Generate a strong password with a password manager. Keep it available securely for the Cloud SQL user creation step.
2. Open **Security → Secret Manager → Create secret**.
3. Set the name to `db-password`, paste the generated password as the secret value, and choose automatic replication (or the Console default).
4. Open the new secret's **Permissions** tab, click **Grant access**, paste the `it-ticket-triage-run-sa` email as the principal, and select the **Secret Manager Secret Accessor** role. Save.
5. Do not put this password in the source repository, README, or `.env` file.

## 4. Create the Cloud SQL PostgreSQL instance

1. Open **Databases → Cloud SQL → Create instance → PostgreSQL**.
2. Configure the instance:

   | Setting | Value |
   |---|---|
   | Instance ID | `it-ticket-triage-pg` |
   | Database version | PostgreSQL 15 |
   | Edition | Enterprise |
   | Region | `us-central1` |
   | Availability | Single zone |
   | Machine type | Smallest available shared-core tier (the sample CLI guide used `db-f1-micro`) |
   | Storage | HDD, 10 GB; disable automatic storage increase if offered |
   | Public IP | Enabled for the Cloud SQL connector; do not add authorized network ranges |
   | Backups / point-in-time recovery | Off for this disposable POC |
   | Deletion protection | Off so cleanup can delete the instance |

   Check the Console's current estimate and available machine tiers before creating the instance; availability and prices can change.
3. Wait until the instance is ready. Open its **Overview** page and copy the **Connection name**. It has the form `PROJECT_ID:us-central1:it-ticket-triage-pg`; copy it from the page rather than typing it, and enter it in Cloud Run in later steps.
4. Open the instance's **Databases** page and create a database named `it-ticket-triage`.
5. Open **Users → Add user account**. Create a built-in database user named `it_ticket_triage_app` and use the exact password stored in Secret Manager.
6. Open **Cloud SQL Studio**. Connect to database `postgres` as the PostgreSQL administrator and run:

   ```sql
   ALTER DATABASE "it-ticket-triage" OWNER TO it_ticket_triage_app;
   ```

   This gives the application user ownership needed by the one-time schema initialization. Do not continue until the database and user exist and this statement succeeds.

## 5. Connect the source repository and build the container

The Cloud Build Console builds from a connected source repository. If the POC is inside a larger repository, configure the trigger's Dockerfile path **and build context** to the `POC_4_IT_SUPPORT_TICKET_TRIAGE` directory. Do not add the ignored `data/` folder to Git; the Docker build generates its own synthetic input files.

1. Make sure the project source, including `Dockerfile`, `pyproject.toml`, `scripts/`, and `it_support_ticket_triage/`, is pushed to the branch you intend to deploy.
2. Open **Cloud Build → Repositories** and connect the GitHub repository if it is not already connected. Complete the GitHub authorization flow.
3. Open **Artifact Registry → Repositories → Create repository**. Name it `it-ticket-triage-poc-images`, choose **Docker** as the format, and select `us-central1`.
4. Open **Cloud Build → Triggers → Create trigger**:
   - Give it a name such as `it-ticket-triage-poc-build`.
   - Choose the connected repository and the branch to deploy.
   - Choose a push event, or configure a manual trigger if you do not want every push to build.
   - Select **Dockerfile** as the build configuration. Set the Dockerfile location to `POC_4_IT_SUPPORT_TICKET_TRIAGE/Dockerfile` and the build context to `POC_4_IT_SUPPORT_TICKET_TRIAGE` (for a repository whose root is already this POC, use `Dockerfile` and `.`).
   - Set the image destination to an Artifact Registry repository in `us-central1`, for example repository `it-ticket-triage-poc-images`, image `it-ticket-triage`, and a unique tag such as the commit SHA.
5. Save the trigger, then select **Run** on the trigger to build the branch. Wait for the build to show **Success**.
6. Open **Artifact Registry → Repositories → it-ticket-triage-poc-images** and copy the full URI of the image built in the successful build, including its tag or digest. Use that same image for both the database job and the Cloud Run service.

If the build fails while pushing the image, open **IAM & Admin → IAM** and ensure the Cloud Build service account used by the build has **Artifact Registry Writer** on the `it-ticket-triage-poc-images` repository. Then rerun the build.

## 6. Initialize the database with a Cloud Run Job

The job uses the built image and runs `scripts/init_db.py --reset`. It creates the tables and loads 4 teams, 14 FAQ articles, and 40 synthetic tickets. Running it again resets and reloads those POC tables.

1. Open **Cloud Run → Jobs → Create job**.
2. Set the job name to `it-ticket-triage-db-init`, select the same region as the SQL instance (`us-central1`), and select the image URI built in Step 5.
3. Expand **Containers, Variables & Secrets** (wording may vary) and configure:
   - **Container command:** `python`
   - **Arguments:** `scripts/init_db.py` and `--reset`
   - **Environment variables:**
     - `GOOGLE_CLOUD_PROJECT` = your project ID
     - `GOOGLE_CLOUD_LOCATION` = `us-central1`
     - `INSTANCE_CONNECTION_NAME` = the Cloud SQL connection name copied in Step 4
     - `DB_USER` = `it_ticket_triage_app`
     - `DB_NAME` = `it-ticket-triage`
     - `DB_BACKEND` = `cloudsql`
     - `USE_LLM` = `false`
   - **Secret environment variable:** expose Secret Manager secret `db-password`, version `latest`, as `DB_PASSWORD`.
   - **Retries:** `0`; **Task timeout:** `10 minutes`.
4. Under **Security**, set the service account to `it-ticket-triage-run-sa`.
5. Create the job. Open it and select **Run**. Wait for the execution to finish successfully before proceeding.
6. If it fails, open the execution's logs. Check the Cloud SQL connection name, `it-ticket-triage-run-sa`'s Cloud SQL Client permission, the secret value versus the SQL user password, and the `it-ticket-triage` database ownership.

## 7. Deploy the Cloud Run service

1. Open **Cloud Run → Services → Deploy container** (or **Create service**).
2. Select the same Artifact Registry image URI used by the database job.
3. Set the service name to `it-ticket-triage-poc` and region to `us-central1`.
4. Under **Security**, set the service identity to `it-ticket-triage-run-sa`.
5. Configure these environment variables:
   - `GOOGLE_GENAI_USE_VERTEXAI` = `TRUE`
   - `GOOGLE_CLOUD_PROJECT` = your project ID
   - `GOOGLE_CLOUD_LOCATION` = `us-central1`
   - `INSTANCE_CONNECTION_NAME` = the Cloud SQL connection name copied in Step 4
   - `DB_USER` = `it_ticket_triage_app`
   - `DB_NAME` = `it-ticket-triage`
   - `DB_BACKEND` = `cloudsql`
   - `USE_LLM` = `true`
6. Add the Secret Manager environment variable `DB_PASSWORD` from secret `db-password`, version `latest`.
7. Set **Maximum number of instances** to `2` for the POC. Keep the Cloud Run service private unless you intentionally choose the temporary public-access option below.
8. Deploy the service and wait for the revision to become ready.

## 8. Run the app

The Cloud Run Console shows the service URL under **Cloud Run → Services → it-ticket-triage-poc**.

**Private option (recommended):** On the service's **Permissions** tab, grant your Google account **Cloud Run Invoker**. Use **Test** in the Cloud Run Console to send a `POST` request to the triage endpoint. The path is the `POST` route defined in the FastAPI app under `it_support_ticket_triage/backend/` (for example `/triage`); check the route there before testing. Use JSON such as:

```json
{
  "subject": "VPN not connecting",
  "description": "The VPN times out when I connect from home."
}
```

Set the request's `Content-Type` to `application/json`. The response contains the suggested category, priority, knowledge-base article, and routing decision. The private UI at `/` may require an authenticated request; use the Console's authenticated test facility for API calls, or the temporary public option if you specifically need to use the browser UI.

**Temporary browser UI option (less secure):** In **Cloud Run → Services → it-ticket-triage-poc → Permissions**, grant `allUsers` the **Cloud Run Invoker** role (or use the Console's **Allow unauthenticated invocations** action). Then open the service URL in a browser, enter a subject and description, and select **Triage ticket**. This makes both the UI and API publicly reachable and can incur Gemini charges if abused. Use synthetic data only. After testing, remove the `allUsers` principal from the service's **Permissions** tab and verify that unauthenticated access is no longer allowed.

To try a sample manually, copy a subject and description from your local reference file `data/sample_tickets.json` into the form or API request. This file is not sent to Cloud Build or used by the application.

Gemini classification can vary between requests. Priority and routing rules remain deterministic. If the result reports `keyword_fallback` instead of `gemini`, check the Cloud Run revision logs, Vertex AI API enablement, `it-ticket-triage-run-sa`'s Vertex AI User role, project/region settings, and model availability.

## 9. Delete the Google Cloud resources when finished

**Do this immediately when finished to stop ongoing charges.** In the Google Cloud Console, confirm that you are in the dedicated POC project before deleting resources:

1. **Cloud Run → Services → it-ticket-triage-poc → Delete.**
2. **Cloud Run → Jobs → it-ticket-triage-db-init → Delete.**
3. **Cloud SQL → Instances → it-ticket-triage-pg → Delete.** Confirm the deletion. This is the most important step for stopping the instance's ongoing charges.
4. **Security → Secret Manager → db-password → Delete.**
5. **Artifact Registry → Repositories → it-ticket-triage-poc-images → Delete.**
6. **IAM & Admin → Service Accounts → it-ticket-triage-run-sa → Delete.**
7. Open **Cloud Build → History** and note any Cloud Build log/source bucket associated only with this POC. In **Cloud Storage → Buckets**, delete only buckets created for this POC; do not delete buckets used by other projects. Also delete the Cloud Build trigger (**Cloud Build → Triggers**) so a later push does not rebuild the image.
8. Check **Cloud Run**, **Cloud SQL**, **Artifact Registry**, **Secret Manager**, and **Cloud Storage** in the selected project to verify the POC resources are gone. Review **Billing → Reports** for delayed charges.

**Most complete cleanup for a dedicated POC project:** open **IAM & Admin → Settings → Shut down**, verify the project ID, and shut down the project. This removes its resources; do this only if nothing else in the project needs to be retained. Budget alerts do not stop or delete resources.

## Security and limits

- Keep the service private unless you deliberately accept the risk of a public POC endpoint. Do not use real tickets or personal data.
- Ticket text is untrusted. Gemini is instructed to classify rather than follow ticket instructions; deterministic routing and confidence thresholds are safeguards, not a production security boundary.
- `it_ticket_triage_log` stores full ticket text and triage results in Cloud SQL. Define retention and access controls before using non-synthetic data.
- Thresholds and response targets in `config/settings.py` are assumed POC values, not official service-level agreements.
