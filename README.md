# Customer Remark Web App

Search and maintain organization-level customer remarks. Fields: CTRLOrgcode, Customer, Remark1, Remark2, Remark3.

Search matches **company name (Customer) only**. Pasted text is stripped to letters automatically. Click a result cell to copy its value.

## Ask (wiki + Files + SOPs + toolkit tables)

The **Ask** tool is the knowledge hub. It searches wiki notes, structured SOP pages, uploaded `.docx` / `.xlsx` / images, customer remarks, feedback cases, and GCA feedback. ICB stations and UNLOCODE are queried live when the question looks like a port, agent, or location lookup.

### Obsidian vault (authoring)

Keep writing in Obsidian, then import a zip into Ask. Suggested folders:

- `00 Inbox/` raw dumps
- `SOPs/` narrative process notes (the SOP editor stays the operational step list)
- `Customers/` article-style customer knowledge
- `LCL/`, `GCA/`, `ICB/`, `UNLOCODE/`
- `Attachments/` images

Use YAML frontmatter (`title`, `tags`) and `[[wikilinks]]`. One topic per note. Convert PDFs to markdown before import. Do not zip `.obsidian/`, `.trash/`, or `.git/`. Do not paste UNLOCODE/ICB CSVs into notes; those tables already live in SearchBar.

Keep secrets out of the vault. The zip is stored on the server and note text is stored in Postgres.

### Update knowledge from Ask

Users can maintain the published wiki without opening Obsidian:

- **New note** / **edit** / **delete** in the Ask knowledge pane (markdown). Saves immediately and reindexes that note.
- **Upload** a `.md` note, a vault `.zip`, or a `.docx` / `.xlsx` / image (files go to the existing Files library and are indexed).
- **Import vault** replaces vault-origin notes by path. Notes you edited in Ask (`origin=app`) are kept unless you import with replace.

Online edits update MALSTAR_Toolkit only. They do not write back to a laptop Obsidian vault unless you copy the markdown out.

- Saving an SOP, uploading a file, or saving a wiki note updates the PostgreSQL `tsvector` index automatically.
- Use **Rebuild index** if older files were added before this feature.
- Without Azure OpenAI, Ask returns matching excerpts and citations (opens the source in Ask).
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
