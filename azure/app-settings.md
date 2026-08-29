# Azure App Service settings (MALSTAR-Toolkit)

This app is a **Linux Python 3.12 Web App** deployed from **GitHub** (Oryx / `SCM_DO_BUILD_DURING_DEPLOYMENT=true`). It is **not** the container script in `deploy.ps1`.

Database: **Azure Database for PostgreSQL Flexible Server**. Uploads stay on App Service storage.

Startup command (Configuration → General settings). Keep this exact string:

```
gunicorn --bind=0.0.0.0:8000 --chdir backend --workers 1 --threads 8 --timeout 120 app:app
```

Do not use `source`, `antenv/bin/gunicorn`, or `WEBSITES_PORT=8080` on this code-deploy app.

## 1. Create Flexible Server

Discover the live app’s resource group and region (`deploy.ps1` names are stale):

```bash
az webapp list --query "[?name=='MALSTAR-Toolkit'].{name:name, rg:resourceGroup, loc:location}" -o table
```

Create Postgres 16 in the **same** group and region. F1 App Service has no VNet, so use public TLS and Azure’s “allow Azure services” rule (`0.0.0.0`):

```bash
az postgres flexible-server create \
  --resource-group <RG> \
  --name malstar-pg \
  --location <same as Web App> \
  --version 16 \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --admin-user malstaradmin \
  --admin-password '<strong password>' \
  --public-access 0.0.0.0 \
  --yes

az postgres flexible-server db create \
  --resource-group <RG> \
  --server-name malstar-pg \
  --database-name malstar
```

Allow the machine that will run the copy script (your laptop or CVM):

```bash
az postgres flexible-server firewall-rule create \
  --resource-group <RG> \
  --name malstar-pg \
  --rule-name AllowCopyClient \
  --start-ip-address <YOUR_IP> \
  --end-ip-address <YOUR_IP>
```

Do not open `0.0.0.0–255.255.255.255`. Flexible Server usernames are `malstar`, not `malstar@malstar-pg`.

Create a non-admin login (psql as `malstaradmin`):

```sql
CREATE USER malstar WITH PASSWORD '<app password>';
GRANT CONNECT ON DATABASE malstar TO malstar;
GRANT USAGE, CREATE ON SCHEMA public TO malstar;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO malstar;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO malstar;
```

After the first app start (or copy script), also:

```sql
GRANT ALL ON ALL TABLES IN SCHEMA public TO malstar;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO malstar;
```

Connection string:

```
postgresql://malstar:<url-encoded-password>@malstar-pg.postgres.database.azure.com:5432/malstar?sslmode=require
```

`sslmode=require` is mandatory.

## 2. Application settings

Keep:

| Name | Value |
| --- | --- |
| `UPLOAD_DIR` | `/home/data/uploads` |
| `LOG_PATH` | `/home/data/malstar_toolkit.log` |
| `WEBSITES_ENABLE_APP_SERVICE_STORAGE` | `true` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |
| `FLASK_DEBUG` | `false` |
| `CORS_ORIGINS` | *(empty)* |

Change:

```bash
az webapp config appsettings set \
  --resource-group <RG> \
  --name MALSTAR-Toolkit \
  --settings DATABASE_URL='postgresql://malstar:...@malstar-pg.postgres.database.azure.com:5432/malstar?sslmode=require'

az webapp config appsettings delete \
  --resource-group <RG> \
  --name MALSTAR-Toolkit \
  --setting-names DATABASE_PATH
```

Optional Ask LLM settings are unchanged: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`.

Oryx installs from **repo-root** `requirements.txt` and `backend/requirements.txt`. Both must list `psycopg[binary,pool]`. GitHub Actions does not need `DATABASE_URL` at build time.

## 3. Cutover order (avoid a crash loop)

Postgres-only code will not start without `DATABASE_URL`.

1. Create Flexible Server (section 1).
2. Deploy this codebase (Oryx installs psycopg).
3. Copy CVM `backend/customer_remark.db` into Flexible Server (do not copy Azure’s empty SQLite over live CVM data unless you have confirmed Azure is newer):

```powershell
cd backend
python scripts/sqlite_to_postgres.py `
  --sqlite customer_remark.db `
  --database-url "postgresql://malstar:...@malstar-pg.postgres.database.azure.com:5432/malstar?sslmode=require"
```

4. Set `DATABASE_URL`, delete `DATABASE_PATH`, restart the Web App.
5. Confirm `/api/health` returns 200 (database ping). Then check remarks, leave, dashboard, file download, Ask.

If you cannot deploy and change settings in one step: set `DATABASE_URL` first (old SQLite code ignores it), deploy the Postgres-only commit, then delete `DATABASE_PATH`.

Copy `uploads/` to `/home/data/uploads` separately if files live only on the CVM. Keep the old `.db` as a backup for several days.

## 4. Health check and scale

Portal: Monitoring → Health check → `/api/health`. That path now fails with 503 if Postgres is unreachable.

Keep **one instance**. Postgres can scale out; `/home/data/uploads` cannot until it is an Azure Files mount.

Keep `--workers 1 --threads 8` on F1. The app pool max is 10 so Burstable `max_connections` is not exhausted.

Always On and custom domains are plan-SKU limits, not database limits. Entra Easy Auth is unchanged.

## 5. Do not use deploy.ps1 for this app

`azure/deploy.ps1` builds a **container** named `autorating-web` and still sets `DATABASE_PATH`. MALSTAR-Toolkit is GitHub code deploy plus Flexible Server as above.
