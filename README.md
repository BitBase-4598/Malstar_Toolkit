# Customer Remark Web App

Search and maintain organization-level customer remarks. Fields: CTRLOrgcode, Customer, Remark1, Remark2, Remark3.

Search matches **company name (Customer) only**. Pasted text is stripped to letters automatically. Click a result cell to copy its value.

## Local development

1. Run `run-backend.bat`.
2. Run `run-frontend.bat` in a second terminal.
3. Open `http://localhost:5173`.

CSV headers must be: `CTRLOrgcode,Customer,Remark1,Remark2,Remark3`. Existing rows are updated by the combined key CTRLOrgcode + Customer.

If replacing the previous project, delete the old SQLite database because its schema is different. The new database is `backend/customer_remark.db`.

## Docker

Build and run the production image locally:

```bash
docker compose up --build
```

Then open `http://localhost:8080`. SQLite is stored in the `sqlite-data` volume at `/home/data/customer_remark.db`.

## Azure App Service

Deploy as a **Linux** Web App with a **custom container**. See [azure/app-settings.md](azure/app-settings.md) for required settings.

From a machine logged in with Azure CLI (`az login`):

```powershell
.\azure\deploy.ps1
```

Use a **single instance**. SQLite is not safe across scale-out. Persist `/home` (`WEBSITES_ENABLE_APP_SERVICE_STORAGE=true`) so remarks survive restarts.
