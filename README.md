# Customer Remark Web App

Search and maintain organization-level customer remarks. Fields: CTRLOrgcode, Customer, Remark1, Remark2, Remark3.

Search matches **company name (Customer) only**. Pasted text is stripped to letters automatically. Click a result cell to copy its value.

## Ask (Files + SOPs)

The **Ask** sidebar tool searches structured SOP pages and uploaded `.docx` / `.xlsx` files.

- Saving an SOP or uploading a file updates the SQLite FTS5 index automatically.
- Use **Rebuild index** if older files were added before this feature.
- Without Azure OpenAI, Ask returns matching excerpts and citations (opens the SOP or file preview).
- With `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, and `AZURE_OPENAI_CHAT_DEPLOYMENT` set, Ask generates an answer from those excerpts. See [azure/app-settings.md](azure/app-settings.md).

On the CVM, rebuild the frontend with `VITE_BASE=/remarks/` so assets load under `/remarks/`.

## Local development

1. Run `run-backend.bat`.
2. Run `run-frontend.bat` in a second terminal.
3. Open `http://localhost:5173`.

CSV headers must be: `CTRLOrgcode,Customer,Remark1,Remark2,Remark3`. Existing rows are updated by the combined key CTRLOrgcode + Customer.

The app uses SQLite. The default file is `backend/malstar.db` (gitignored). Override with `DATABASE_PATH` or `DATABASE_URL=sqlite:///...` in a gitignored `.env` (see `.env.example`).

## Run on this CVM

`start-service.ps1` is the NSSM production start (waitress on port 8080). To build the frontend and start once by hand:

```powershell
cd frontend
npm install
$env:VITE_BASE="/remarks/"
npm run build
cd ..\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
$env:FLASK_HOST="0.0.0.0"
$env:PORT="8080"
$env:FLASK_DEBUG="false"
.\.venv\Scripts\python app.py
```

`backend/gateway.py` listens on port 80 and forwards `/remarks/` to `http://127.0.0.1:8080`.

## Azure App Service

Deploy is **GitHub Actions** on `main`: [`.github/workflows/main_malstar-toolkit.yml`](.github/workflows/main_malstar-toolkit.yml) builds the frontend and deploys the Python app to the Linux Web App `MALSTAR-Toolkit` (Oryx). Runtime is SQLite. Settings and the gunicorn startup command are in [azure/app-settings.md](azure/app-settings.md).

Use a **single instance**. Uploads stay on `/home` (`WEBSITES_ENABLE_APP_SERVICE_STORAGE=true`) and are not safe across scale-out until they are on Azure Files.

## Public access on this Tencent CVM

Cloud security group allows **TCP 80**, not 8080. Customer Remarks is proxied through the existing port-80 service:

- Public: http://111.229.173.46/remarks/
- Local: http://127.0.0.1/remarks/

Time Motion Tracker Pro stays at http://111.229.173.46/
