# Azure App Service settings (MALSTAR-Toolkit)

This app is a **Linux Python 3.12 Web App** deployed from **GitHub** (Oryx / `SCM_DO_BUILD_DURING_DEPLOYMENT=true`). It is **not** the container script in `deploy.ps1`.

Live site: `https://malstar-toolkit-djexgna2eghtgkep.eastasia-01.azurewebsites.net`  
Kudu / SCM: `https://malstar-toolkit-djexgna2eghtgkep.scm.eastasia-01.azurewebsites.net`

If you still have an old App Service `.db`, `backend/scripts/sqlite_to_postgres.py` can copy it once. Otherwise `backend/scripts/live_api_to_postgres.py` copies the public API tables (remarks, leave, logs, ICB, UNLOCODE, GCA, dashboard). It cannot copy `/home` uploads or raw `LclShipments`. The running app no longer opens SQLite.

Database: **Azure Database for PostgreSQL Flexible Server**. Uploads stay on App Service `/home` storage.

Startup command (Configuration → General settings). Keep this exact string:

```
gunicorn --bind=0.0.0.0:8000 --chdir backend --workers 1 --threads 8 --timeout 120 app:app
```

Do not use `source`, `antenv/bin/gunicorn`, or `WEBSITES_PORT=8080` on this code-deploy app.

## 1. Flexible Server (already created)

| Item | Value |
| --- | --- |
| Host | `malstar.postgres.database.azure.com` |
| Port | `5432` |
| App database | `malstar` (created; do not put app tables in the default `postgres` database) |
| App user | `nathan` |
| TLS | `sslmode=require` |

`nathan` can create databases. The default `postgres` database already has an unrelated `public.shipment` test table and an empty `Malstar_PROD` schema. App tables go in the dedicated `malstar` database.

Connection string (URL-encode `$` in the password as `%24`):

```
postgresql://nathan:<url-encoded-password>@malstar.postgres.database.azure.com:5432/malstar?sslmode=require
```

Put that value only in:

- a local gitignored `.env` (for the copy script)
- Azure App Service application settings (`DATABASE_URL`)

Never commit the password, paste it into the PR, or store it in this file.

Allow Azure services (the F1 Web App has no VNet) and the machine that runs the copy script:

```bash
az postgres flexible-server firewall-rule create \
  --resource-group <RG> \
  --name malstar \
  --rule-name AllowCopyClient \
  --start-ip-address <YOUR_IP> \
  --end-ip-address <YOUR_IP>
```

Do not open `0.0.0.0–255.255.255.255`. Flexible Server usernames are `nathan`, not `nathan@malstar`.

After the first migrate / copy, confirm:

```sql
GRANT ALL ON ALL TABLES IN SCHEMA public TO nathan;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nathan;
```

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

Required:

```bash
az webapp config appsettings set \
  --resource-group <RG> \
  --name MALSTAR-Toolkit \
  --settings DATABASE_URL='postgresql://nathan:<url-encoded-password>@malstar.postgres.database.azure.com:5432/malstar?sslmode=require'

az webapp config appsettings delete \
  --resource-group <RG> \
  --name MALSTAR-Toolkit \
  --setting-names DATABASE_PATH
```

`DATABASE_URL` is required. The process exits on boot if it is missing or not a PostgreSQL URL. Delete leftover `DATABASE_PATH`; it is unused.

Optional Ask LLM settings are unchanged: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`.

Optional wiki vault zip size: `WIKI_MAX_ZIP_MB` (default 64). Import the Obsidian zip from the Ask tool.

Oryx installs from **repo-root** `requirements.txt` and `backend/requirements.txt`. Both must list `psycopg[binary,pool]`. GitHub Actions does not need `DATABASE_URL` at build time.

## 3. Historical copy (optional)

Live App Service already uses Azure Flexible Server. There is no SQLite fallback or rollback.

If you still have an old `.db` and need to load it into a fresh database, from a machine on the Flexible Server firewall:

```powershell
cd backend
python scripts/sqlite_to_postgres.py --sqlite <downloaded-customer_remark.db>
```

The script reads `DATABASE_URL` from `.env` if you omit `--database-url`.

To copy from the public APIs instead:

```powershell
cd backend
python scripts/live_api_to_postgres.py --app-url "https://malstar-toolkit-djexgna2eghtgkep.eastasia-01.azurewebsites.net"
```

Compare row counts for `CustomerRemarks`, `LeavePeople`, `LeavePlans`, `ToolkitFiles`, `ActivityLogs`. Confirm `GET /api/health` returns 200, then check remarks, leave, dashboard, file download, Ask, and logs.

Uploads stay on `/home/data/uploads`. They are not moved into Postgres.

## 4. Health check and scale

Portal: Monitoring → Health check → `/api/health`. That path now fails with 503 if Postgres is unreachable.

Keep **one instance**. Postgres can scale out; `/home/data/uploads` cannot until it is an Azure Files mount.

Keep `--workers 1 --threads 8` on F1. The app pool max is 10 so Burstable `max_connections` is not exhausted.

Always On and custom domains are plan-SKU limits, not database limits. Entra Easy Auth is unchanged.

## 5. Do not use deploy.ps1 for this app

`azure/deploy.ps1` builds a **container** named `autorating-web` and is not used for MALSTAR-Toolkit. This app is GitHub code deploy plus Flexible Server as above.
