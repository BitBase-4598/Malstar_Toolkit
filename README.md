# Customer Remark Web App

Search and maintain organization-level customer remarks. Fields: CTRLOrgcode, Customer, Remark1, Remark2, Remark3.

Search matches **company name (Customer) only**. Pasted text is stripped to letters automatically. Click a result cell to copy its value.

## Ask (Files + SOPs)

The **Ask** sidebar tool searches structured SOP pages and uploaded `.docx` / `.xlsx` files.

- Saving an SOP or uploading a file updates the PostgreSQL `tsvector` index automatically.
- **Wiki** (branch `MALSTAR-WIKI-TEST`) builds a searchable page layer from remarks, SOPs, files, cases, and GCA feedback. It does not wiki-ify LCL or UNLOCODE rows. Keyword search is default; set `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` to store JSON embeddings and rerank.
- Use **Rebuild index** if older files were added before this feature.
- Without Azure OpenAI, Ask returns matching excerpts and citations (opens the SOP or file preview).
- With `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, and `AZURE_OPENAI_CHAT_DEPLOYMENT` set, Ask generates an answer from those excerpts. See [azure/app-settings.md](azure/app-settings.md).

On the CVM, rebuild the frontend with `VITE_BASE=/remarks/` so assets load under `/remarks/`.

## Local development

1. Run `run-backend.bat`.
2. Run `run-frontend.bat` in a second terminal.
3. Open `http://localhost:5173`.

CSV headers must be: `CTRLOrgcode,Customer,Remark1,Remark2,Remark3`. Existing rows are updated by the combined key CTRLOrgcode + Customer.

PostgreSQL is required. Set `DATABASE_URL` in a gitignored `.env` (see `.env.example`). The app will not start without a `postgres://` or `postgresql://` URL.

## Run on this machine (no Docker)

Docker is optional. On a Windows CVM you can serve the built SPA from Flask:

```powershell
cd frontend
npm install
npm run build
cd ..\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
$env:FLASK_HOST="0.0.0.0"
$env:PORT="8080"
$env:FLASK_DEBUG="false"
.\.venv\Scripts\python app.py
```

Then open `http://localhost:8080` on the CVM, or `http://<cvm-ip>:8080` from another machine (port 8080 must be allowed in the firewall).

## Docker

Build and run the production image locally:

```bash
docker compose up --build
```

Then open `http://localhost:8080`. Docker Compose and local `python app.py` both require `DATABASE_URL` (Compose default: `postgresql://malstar:malstar@postgres:5432/malstar`).

`scripts/sqlite_to_postgres.py` is an archival one-shot reader for an old `.db` file. New runtimes do not open SQLite. `python scripts/live_api_to_postgres.py` copies public App Service APIs into Postgres. Azure settings are in [azure/app-settings.md](azure/app-settings.md).

## Azure App Service

Deploy as a **Linux** Web App with a **custom container**. See [azure/app-settings.md](azure/app-settings.md) for required settings.

From a machine logged in with Azure CLI (`az login`):

```powershell
.\azure\deploy.ps1
```

Use a **single instance**. Uploads stay on `/home` (`WEBSITES_ENABLE_APP_SERVICE_STORAGE=true`) and are not safe across scale-out until they are on Azure Files.

## Public access on this Tencent CVM

Cloud security group allows **TCP 80**, not 8080. Customer Remarks is proxied through the existing port-80 service:

- Public: http://111.229.173.46/remarks/
- Local: http://127.0.0.1/remarks/

Time Motion Tracker Pro stays at http://111.229.173.46/
