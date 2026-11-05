# IT Support Ticket Triage & Routing Assistant (POC)

Submit an IT ticket subject and description to get a suggested **category**, **priority**, **knowledge-base article**, and **routing decision**. Gemini on Vertex AI classifies tickets. Priority, knowledge lookup, and team routing use deterministic rules. Low-confidence or conflicting tickets are sent to `NEEDS_HUMAN_TRIAGE`.

This guide uses the **Google Cloud Console** for setup, deployment, and cleanup, and **Cloud Shell** (the terminal built into the Console, no local install) for testing the running service. You do not need a local Python environment. You will need the project source in a GitHub repository connected to Cloud Build.

In every command and path below, replace `PROJECT_ID` with your own project ID (shown in the Console project picker).

## Using the gcloud CLI instead of the Console

Every Console step below has a collapsed **gcloud equivalent** section. You can follow the guide with either method, or mix them. Use **Cloud Shell** (terminal icon at the top right of the Console, `gcloud` already installed and signed in) or a local terminal with the [gcloud CLI](https://cloud.google.com/sdk/docs/install) after `gcloud auth login`.

Set these variables once per terminal session. All later commands use them. Shell variables are lost when the terminal closes, so set them again in a new session.

```bash
export PROJECT_ID=your-project-id
export REGION=us-central1
export SA_NAME=it-ticket-triage-run-sa
export SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
export REPO=it-ticket-triage-poc-images
export IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/it-ticket-triage:v1"
gcloud config set project "$PROJECT_ID"
```

**Note:** the commands are the CLI equivalents of the Console steps. Flags and defaults change between gcloud releases. If a command rejects a flag, run it with `--help`. Never paste passwords into the README, the repository or chat.

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

<details>
<summary><b>gcloud equivalent: Step 1</b></summary>

```bash
# Create the project and link billing (skip if you already created it in the Console).
# Find your billing account ID with: gcloud billing accounts list
gcloud projects create "$PROJECT_ID"
gcloud billing projects link "$PROJECT_ID" --billing-account=BILLING_ACCOUNT_ID

# Enable the APIs
gcloud services enable \
  sqladmin.googleapis.com \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com
```

Budgets are easier in the Console (**Billing → Budgets & alerts**). A CLI version exists (`gcloud billing budgets create`) but needs the Billing Budgets API and extra permissions. Alerts do not cap spending either way.

</details>

## 2. Create the runtime service account

1. Open **IAM & Admin → Service Accounts → Create service account**.
2. Name it `it-ticket-triage-run-sa`; create it without granting any roles on the creation screen. Click **Done**.
3. Confirm it exists in **IAM & Admin → Service Accounts** (check that the project picker shows your POC project) and copy its email: `it-ticket-triage-run-sa@PROJECT_ID.iam.gserviceaccount.com`.
4. Grant it project roles:
   1. Open **IAM & Admin → IAM → Grant access**.
   2. In **New principals**, paste the service account email.
   3. Under **Role**, add these roles (use **Add another role** for each):

      | Role | Why |
      |---|---|
      | **Cloud SQL Client** (`roles/cloudsql.client`) | the app and initialization job connect through the Cloud SQL connector |
      | **Vertex AI User** (`roles/aiplatform.user`) | the app calls Gemini. The Console may label this role **Agent Platform User**; confirm by the role ID `roles/aiplatform.user` |
      | **Logs Writer** (`roles/logging.logWriter`) | the Cloud Build trigger in Step 5 runs as this account and must write build logs |
      | **Artifact Registry Writer** (`roles/artifactregistry.writer`) | the Cloud Build trigger pushes the image as this account |
   4. Click **Save**.

   **Note:** a new service account does **not** appear on the **IAM** page until it has been granted at least one role. If you look for it there before this step, it will not be listed. Use **Service Accounts** to find it, and **Grant access** to give it roles.
5. In Step 3 you will also grant it **Secret Manager Secret Accessor** on the `db-password` secret only. Do not grant the service account project Owner.

   **Security note:** this one account is used for both the build and the running app, so the build roles also apply to the running service. That is acceptable for a short-lived POC. For anything longer, use a separate build service account and keep this one to Cloud SQL Client, Vertex AI User, and the secret.

<details>
<summary><b>gcloud equivalent: Step 2</b></summary>

```bash
gcloud iam service-accounts create "$SA_NAME" \
  --display-name="IT ticket triage runtime"

for ROLE in roles/cloudsql.client roles/aiplatform.user \
            roles/logging.logWriter roles/artifactregistry.writer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" --role="$ROLE" --condition=None
done

# Check: lists the roles granted to the account
gcloud projects get-iam-policy "$PROJECT_ID" \
  --flatten="bindings[].members" \
  --filter="bindings.members:$SA_EMAIL" \
  --format="value(bindings.role)"
```

If the project was created a moment ago, the account may need a few seconds before the role grants succeed. Retry once if you see a "service account does not exist" error.

</details>

## 3. Create and save the database password secret

1. Generate a strong password with a password manager. Keep it available securely for the Cloud SQL user creation step.
2. Open **Security → Secret Manager → Create secret**.
3. Set the name to `db-password`, paste the generated password as the secret value, and choose automatic replication (or the Console default).
4. Open the new secret's **Permissions** tab, click **Grant access**, paste the `it-ticket-triage-run-sa` email as the principal, and select the **Secret Manager Secret Accessor** role. Save.
5. Do not put this password in the source repository, README, or `.env` file.

<details>
<summary><b>gcloud equivalent: Step 3</b></summary>

```bash
# Generate a password and store it straight into Secret Manager.
# It is never printed. Read it back later only when needed (see Step 4).
openssl rand -base64 24 | tr -d '/+=\n' | \
  gcloud secrets create db-password --replication-policy=automatic --data-file=-

# Let the runtime account read this secret only
gcloud secrets add-iam-policy-binding db-password \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor"
```

</details>

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

   **Create page notes (the Console changes often):**
   - The page asks for a **Password**. This sets the password of the default `postgres` administrator user. Click **Generate** (or use your password manager) and store it securely. You need it in item 6 below to open Cloud SQL Studio as `postgres`. Do not put it in chat, the README, or the repository. It is different from the `it_ticket_triage_app` password in the `db-password` secret.
   - The page may offer a **free trial** instance (larger Enterprise Plus machine, no charge for a limited period unless you upgrade) as well as **Sandbox / Development / Production** presets. For a disposable POC either works. Read the page's billing text first. The table above is the low-cost target; if the Console shows different defaults (for example a newer PostgreSQL version or SSD storage), PostgreSQL 15 or later and SSD are fine for this app.
   - After creation, open **Edit** on the instance and check that public IP has no authorized networks and deletion protection is off.
3. Wait until the instance is ready. Open its **Overview** page and copy the **Connection name**. It has the form `PROJECT_ID:us-central1:it-ticket-triage-pg`; copy it from the page rather than typing it, and enter it in Cloud Run in later steps.
4. Open the instance's **Databases** page and create a database named `it-ticket-triage`.
5. Open **Users → Add user account**. Create a built-in database user named `it_ticket_triage_app` and use the exact password stored in Secret Manager.
6. Open **Cloud SQL Studio**. Connect to database `postgres` as the PostgreSQL administrator and run:

   ```sql
   ALTER DATABASE "it-ticket-triage" OWNER TO it_ticket_triage_app;
   ```

   This gives the application user ownership needed by the one-time schema initialization. Do not continue until the database and user exist and this statement succeeds.

<details>
<summary><b>gcloud equivalent: Step 4</b></summary>

```bash
# Admin (postgres) password: choose one and keep it in your password manager.
# Typing it at a hidden prompt keeps it out of your shell history.
read -rs -p "postgres admin password: " ADMIN_PW; echo

gcloud sql instances create it-ticket-triage-pg \
  --database-version=POSTGRES_15 \
  --edition=ENTERPRISE \
  --region="$REGION" \
  --availability-type=zonal \
  --tier=db-f1-micro \
  --storage-type=HDD --storage-size=10GB --no-storage-auto-increase \
  --no-backup \
  --no-deletion-protection \
  --root-password="$ADMIN_PW"

gcloud sql databases create it-ticket-triage --instance=it-ticket-triage-pg

# App user, using the exact password stored in the secret
gcloud sql users create it_ticket_triage_app --instance=it-ticket-triage-pg \
  --password="$(gcloud secrets versions access latest --secret=db-password)"

# Connection name, used by the Cloud Run job and service
export CONN=$(gcloud sql instances describe it-ticket-triage-pg \
  --format="value(connectionName)")
echo "$CONN"        # PROJECT_ID:us-central1:it-ticket-triage-pg

# Give the app user ownership of the database (the ALTER DATABASE step).
# gcloud sql connect needs the psql client, which Cloud Shell has. It asks for the postgres password.
gcloud sql connect it-ticket-triage-pg --user=postgres --database=postgres
#   then at the psql prompt:  ALTER DATABASE "it-ticket-triage" OWNER TO it_ticket_triage_app;
#   then:  \q
```

Notes:
- PostgreSQL 15, HDD and a shared-core tier are the low-cost targets. If the command rejects a value (for example the tier or HDD is not available for your edition), check the options with `gcloud sql tiers list` and `gcloud sql instances create --help`, or use the Console estimate.
- `gcloud sql connect` temporarily authorizes your IP for the session. It does not leave a permanent authorized network. Cloud SQL Studio in the Console works too.
- Run `unset ADMIN_PW` when done.

</details>

## 5. Connect the source repository and build the container

The Cloud Build Console builds from a connected source repository. If the POC is inside a larger repository, configure the trigger's Dockerfile path **and build context** to the `POC_4_IT_SUPPORT_TICKET_TRIAGE` directory. Do not add the ignored `data/` folder to Git; the Docker build generates its own synthetic input files.

1. Make sure the project source, including `Dockerfile`, `pyproject.toml`, `scripts/`, and `it_support_ticket_triage/`, is pushed to the branch you intend to deploy.
2. Open **Cloud Build → Repositories** and connect the GitHub repository if it is not already connected. Complete the GitHub authorization flow.

   **If your repository is missing from the list:** the Cloud Build GitHub app can only see repositories you gave it access to. On GitHub open **Settings → Applications → Installed GitHub Apps → Google Cloud Build → Configure**, set **Repository access** to **All repositories** (or add your repository), save, then refresh the Console. For a repository in a GitHub organization, the app must be installed on that organization, and an organization owner may have to approve it.
3. Open **Artifact Registry → Repositories → Create repository**. Name it `it-ticket-triage-poc-images`, choose **Docker** as the format, and select `us-central1`.
4. Open **Cloud Build → Triggers → Create trigger**:
   - Give it a name such as `it-ticket-triage-poc-build`.
   - Choose the connected repository and the branch to deploy.
   - Choose a push event, or configure a manual trigger if you do not want every push to build.
   - Set the trigger's **Service account** to `it-ticket-triage-run-sa` (it already has Logs Writer and Artifact Registry Writer from Step 2).
   - Leave **Send build logs to GitHub** unchecked. It makes logs visible to anyone with read access to the repository and does not affect where logs are stored.
   - For the build configuration, use **Cloud Build configuration file → Inline** and paste the YAML below. A trigger that runs as a custom service account must say where logs go; without `options.logging` the run fails with `if 'build.service_account' is specified, the build must either (a) specify 'build.logs_bucket'...`. Replace `PROJECT_ID`. If the `Dockerfile` is at the repository root instead of in `POC_4_IT_SUPPORT_TICKET_TRIAGE/`, remove the `dir:` line.

     ```yaml
     steps:
       - name: gcr.io/cloud-builders/docker
         dir: POC_4_IT_SUPPORT_TICKET_TRIAGE
         args:
           - build
           - -t
           - us-central1-docker.pkg.dev/PROJECT_ID/it-ticket-triage-poc-images/it-ticket-triage:$COMMIT_SHA
           - -f
           - Dockerfile
           - .
     images:
       - us-central1-docker.pkg.dev/PROJECT_ID/it-ticket-triage-poc-images/it-ticket-triage:$COMMIT_SHA
     options:
       logging: CLOUD_LOGGING_ONLY
     ```

     The image goes to the Artifact Registry repository in `us-central1`: repository `it-ticket-triage-poc-images`, image `it-ticket-triage`, tag = the commit SHA. (If you choose the plain **Dockerfile** option instead, set the **Image name** field to that same `us-central1-docker.pkg.dev/...` path, replacing the default `gcr.io/...` value, and set **Logging** under **Advanced** to Cloud Logging only if the Console offers it.)
5. Save the trigger, then select **Run** on the trigger to build the branch. Wait for the build to show **Success**.
6. Open **Artifact Registry → Repositories → it-ticket-triage-poc-images** and copy the full URI of the image built in the successful build, including its tag or digest. Use that same image for both the database job and the Cloud Run service.

If the build fails:
- **`does not have permission to write logs to Cloud Logging`:** grant the trigger's service account **Logs Writer** (`roles/logging.logWriter`), wait a minute, and rerun.
- **Permission denied while pushing the image:** grant the trigger's service account **Artifact Registry Writer** on the `it-ticket-triage-poc-images` repository, then rerun.
- **`iam.serviceAccounts.actAs` error:** grant the user who runs the trigger **Service Account User** on `it-ticket-triage-run-sa`.
- **Dockerfile not found:** check the `dir:` value against the real folder in your repository.

<details>
<summary><b>gcloud equivalent: Step 5 (build without a GitHub trigger)</b></summary>

The CLI can build straight from a local folder, so no repository connection or trigger is needed. In Cloud Shell, get the code first (`git clone <your repo URL>`), then run the commands from the folder that contains the `Dockerfile`.

```bash
cd POC_4_IT_SUPPORT_TICKET_TRIAGE      # the folder with the Dockerfile

# Docker repository for the image
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker --location="$REGION"

# Build config. The 'EOF' quotes stop the shell from expanding ${_IMAGE}.
cat > /tmp/cloudbuild-triage.yaml <<'EOF'
steps:
  - name: gcr.io/cloud-builders/docker
    args: ["build", "-t", "${_IMAGE}", "-f", "Dockerfile", "."]
images:
  - "${_IMAGE}"
options:
  logging: CLOUD_LOGGING_ONLY
EOF

gcloud builds submit . \
  --region="$REGION" \
  --config=/tmp/cloudbuild-triage.yaml \
  --substitutions=_IMAGE="$IMAGE" \
  --service-account="projects/$PROJECT_ID/serviceAccounts/$SA_EMAIL"

# Confirm the image exists
gcloud artifacts docker images list "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO"
```

`options.logging: CLOUD_LOGGING_ONLY` is required because the build runs as a custom service account (see the error notes above). The image tag is `v1`, set in the `IMAGE` variable. Change the tag in `IMAGE` for a rebuild so each image stays identifiable. For the GitHub trigger itself, use the Console steps above, or `gcloud builds triggers create github --help` if you want to script it.

</details>

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

<details>
<summary><b>gcloud equivalent: Step 6</b></summary>

```bash
gcloud run jobs create it-ticket-triage-db-init \
  --image="$IMAGE" \
  --region="$REGION" \
  --service-account="$SA_EMAIL" \
  --command=python \
  --args="scripts/init_db.py,--reset" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,INSTANCE_CONNECTION_NAME=$CONN,DB_USER=it_ticket_triage_app,DB_NAME=it-ticket-triage,DB_BACKEND=cloudsql,USE_LLM=false" \
  --set-secrets="DB_PASSWORD=db-password:latest" \
  --max-retries=0 \
  --task-timeout=10m

# Run it and wait for it to finish
gcloud run jobs execute it-ticket-triage-db-init --region="$REGION" --wait
```

`CONN` comes from Step 4's gcloud section. In a new terminal, set it again with the `gcloud sql instances describe` command from there. Logs of a failed run: **Cloud Run → Jobs → it-ticket-triage-db-init → Logs**.

</details>

## 7. Deploy the Cloud Run service

1. Open **Cloud Run → Services → Deploy container** (or **Create service**).
2. Select the same Artifact Registry image URI used by the database job.
3. Set the service name to `it-ticket-triage-poc` and region to `us-central1`.
4. Under **Security**, set the service identity to `it-ticket-triage-run-sa`.
5. Configure these environment variables:
   - `GOOGLE_GENAI_USE_VERTEXAI` = `TRUE`
   - `GOOGLE_CLOUD_PROJECT` = your project ID
   - `GOOGLE_CLOUD_LOCATION` = `global`. This is the location used for the **Gemini** call only; the service, Cloud SQL and Artifact Registry stay in `us-central1`. The app's default of `us-central1` returned `404 NOT_FOUND` for the model in this project.
   - `INSTANCE_CONNECTION_NAME` = the Cloud SQL connection name copied in Step 4
   - `DB_USER` = `it_ticket_triage_app`
   - `DB_NAME` = `it-ticket-triage`
   - `DB_BACKEND` = `cloudsql`
   - `USE_LLM` = `true`
   - `GEMINI_MODEL` = `gemini-3.8-flash` (also the default in `config/settings.py`, and the same model POC 3 uses with `GOOGLE_CLOUD_LOCATION=global`). The earlier default `gemini-2.5-flash` returned `404 ... Publisher model ... was not found` in this project. If your project can't use the model either, copy another ID from **Vertex AI → Model Garden** and set it here.
6. Add the Secret Manager environment variable `DB_PASSWORD` from secret `db-password`, version `latest`.
7. Set **Maximum number of instances** to `2` for the POC. Keep the Cloud Run service private unless you intentionally choose the temporary public-access option below.
8. Deploy the service and wait for the revision to become ready.

<details>
<summary><b>gcloud equivalent: Step 7</b></summary>

```bash
gcloud run deploy it-ticket-triage-poc \
  --image="$IMAGE" \
  --region="$REGION" \
  --service-account="$SA_EMAIL" \
  --no-allow-unauthenticated \
  --max-instances=2 \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=global,INSTANCE_CONNECTION_NAME=$CONN,DB_USER=it_ticket_triage_app,DB_NAME=it-ticket-triage,DB_BACKEND=cloudsql,USE_LLM=true,GEMINI_MODEL=gemini-3.8-flash" \
  --set-secrets="DB_PASSWORD=db-password:latest"

# Service URL
gcloud run services describe it-ticket-triage-poc --region="$REGION" \
  --format="value(status.url)"
```

`--no-allow-unauthenticated` keeps the service private. `GOOGLE_CLOUD_LOCATION=global` applies to the Gemini call only; the service itself runs in `$REGION`.

</details>

## 8. Run the app

The Cloud Run Console shows the service URL under **Cloud Run → Services → it-ticket-triage-poc**.

**Private option (recommended):** keep the service private and call it with your own identity.

1. Grant your Google account **Cloud Run Invoker**. The **Permissions** panel has moved in newer Consoles: in **Cloud Run → Services** tick the service's checkbox and open the **Permissions** panel (toolbar or info panel), or use Cloud Shell:

   ```bash
   gcloud run services add-iam-policy-binding it-ticket-triage-poc \
     --region us-central1 \
     --member="user:YOUR_EMAIL" \
     --role="roles/run.invoker"
   ```

   As project owner you may already have access.
2. Open **Cloud Shell** (the terminal icon at the top right of the Console). The project is already selected. Send a test ticket to the `POST /triage` route. Replace `SERVICE_URL` with the URL shown on the service page:

   ```bash
   curl -X POST "SERVICE_URL/triage" \
     -H "Authorization: bearer $(gcloud auth print-identity-token)" \
     -H "Content-Type: application/json" \
     -d '{"subject": "VPN not connecting", "description": "The VPN times out when I connect from home."}'
   ```

   Posting to the bare URL (`/`) returns `{"detail":"Method Not Allowed"}`; the route is `/triage`. To see every route and its fields, open `SERVICE_URL/docs` (or `/openapi.json`) with the same token, or look for `@app.post` under `it_support_ticket_triage/backend/`.
3. The response contains the suggested category, priority, knowledge-base article, and routing decision. A working run looks like this (values vary):

   ```text
   intake.source = "gemini", category = "network", category_confidence ~ 0.95
   knowledge_base.kb_id = "KB01"
   routing.decision = "ASSIGN_TEAM", team = "Network Operations"
   ```
4. To use the browser UI at `/` without making the service public, run a local proxy from a terminal that has `gcloud` and is signed in, then open `http://localhost:8080`:

   ```bash
   gcloud run services proxy it-ticket-triage-poc --region us-central1 --port 8080
   ```

**Temporary browser UI option (less secure):** In **Cloud Run → Services → it-ticket-triage-poc → Permissions**, grant `allUsers` the **Cloud Run Invoker** role (or use the Console's **Allow unauthenticated invocations** action). Then open the service URL in a browser, enter a subject and description, and select **Triage ticket**. This makes both the UI and API publicly reachable and can incur Gemini charges if abused. Use synthetic data only. After testing, remove the `allUsers` principal from the service's **Permissions** tab and verify that unauthenticated access is no longer allowed.

<details>
<summary><b>gcloud equivalent: Step 8 (access control)</b></summary>

The private-option commands above are already CLI. For the temporary public option, and to turn it off again:

```bash
# Allow anyone to call the service (temporary, synthetic data only)
gcloud run services add-iam-policy-binding it-ticket-triage-poc \
  --region="$REGION" --member=allUsers --role=roles/run.invoker

# Turn it off again
gcloud run services remove-iam-policy-binding it-ticket-triage-poc \
  --region="$REGION" --member=allUsers --role=roles/run.invoker

# Check who can invoke the service now
gcloud run services get-iam-policy it-ticket-triage-poc --region="$REGION"
```

Organization policy may block `allUsers`. If the command fails with a policy error, use the proxy command in the private option instead.

</details>

To try a sample manually, copy a subject and description from your local reference file `data/sample_tickets.json` into the form or API request. This file is not sent to Cloud Build or used by the application.

Gemini classification can vary between requests. Priority and routing rules remain deterministic.

### If the result says `keyword_fallback` instead of `gemini`

The app still works, but Gemini was skipped because the call failed. Find the reason in the service logs (**Cloud Run → it-ticket-triage-poc → Logs**, severity **Error**), or from Cloud Shell:

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="it-ticket-triage-poc" AND severity>=ERROR' \
  --limit 1 --freshness 30m --format="value(textPayload)" | tail -n 8
```

| Error in the log | Fix |
|---|---|
| `404 NOT_FOUND ... locations/us-central1/publishers/google/models/...` | set `GOOGLE_CLOUD_LOCATION=global` on the service |
| the same 404 but already `locations/global` | the model ID is unavailable: set `GEMINI_MODEL=gemini-3.8-flash`, or another ID from Model Garden |
| `403` / permission denied | grant `it-ticket-triage-run-sa` **Vertex AI User** (`roles/aiplatform.user`) |
| API not enabled | enable the **Vertex AI API** |

Change variables on a running service without rebuilding, then retest (check the new revision with `gcloud run services describe it-ticket-triage-poc --region us-central1`):

```bash
gcloud run services update it-ticket-triage-poc --region us-central1 \
  --update-env-vars GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL=gemini-3.8-flash
```

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

<details>
<summary><b>gcloud equivalent: Step 9 (cleanup)</b></summary>

Confirm `gcloud config get-value project` shows the POC project before deleting anything. `--quiet` skips the confirmation prompts, so check the names first.

```bash
gcloud run services delete it-ticket-triage-poc --region="$REGION" --quiet
gcloud run jobs delete it-ticket-triage-db-init --region="$REGION" --quiet

# Most important: stops the instance charges
gcloud sql instances delete it-ticket-triage-pg --quiet

gcloud secrets delete db-password --quiet
gcloud artifacts repositories delete "$REPO" --location="$REGION" --quiet
gcloud iam service-accounts delete "$SA_EMAIL" --quiet

# Only if you created a trigger in the Console
gcloud builds triggers list --region="$REGION"
gcloud builds triggers delete it-ticket-triage-poc-build --region="$REGION"

# Look for leftover Cloud Build source buckets, and delete only ones made for this POC
gcloud storage buckets list --format="value(name)"

# Verify nothing is left
gcloud run services list --region="$REGION"
gcloud run jobs list --region="$REGION"
gcloud sql instances list
gcloud secrets list
gcloud artifacts repositories list --location="$REGION"
```

If the instance delete fails because deletion protection is on, turn it off first:

```bash
gcloud sql instances patch it-ticket-triage-pg --no-deletion-protection
```

**Most complete cleanup:** delete the whole project, which removes every resource in it. Do this only if nothing in the project needs to be kept. The project enters a short recovery period before it is permanently removed.

```bash
gcloud projects delete "$PROJECT_ID"
```

</details>

## Security and limits

- Keep the service private unless you deliberately accept the risk of a public POC endpoint. Do not use real tickets or personal data.
- Ticket text is untrusted. Gemini is instructed to classify rather than follow ticket instructions; deterministic routing and confidence thresholds are safeguards, not a production security boundary.
- `it_ticket_triage_log` stores full ticket text and triage results in Cloud SQL. Define retention and access controls before using non-synthetic data.
- Thresholds and response targets in `config/settings.py` are assumed POC values, not official service-level agreements.
