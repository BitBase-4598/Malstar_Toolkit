# Azure App Service settings (MALSTAR-Toolkit)

This app is a **Linux Python 3.12 Web App** deployed from **GitHub** (Oryx / `SCM_DO_BUILD_DURING_DEPLOYMENT=true`). It is **not** the container script in `deploy.ps1`.

Live site: `https://malstar-toolkit-djexgna2eghtgkep.eastasia-01.azurewebsites.net`  
Kudu / SCM: `https://malstar-toolkit-djexgna2eghtgkep.scm.eastasia-01.azurewebsites.net`

The running app uses **SQLite only**. Default file is `backend/malstar.db`. Override with `DATABASE_PATH` or `DATABASE_URL=sqlite:///...`. A leftover `postgresql://` `DATABASE_URL` will fail on boot.

Do **not** merge this cutover to `main` until App Service `DATABASE_URL` is changed to a persisted SQLite path (for example `/home/data/malstar.db`) and a copied `.db` is placed there. Until then, production can keep Azure Flexible Server.

Startup command (Configuration → General settings). Keep this exact string:

```
gunicorn --bind=0.0.0.0:8000 --chdir backend --workers 1 --threads 8 --timeout 120 app:app
```

Do not use `source`, `antenv/bin/gunicorn`, or `WEBSITES_PORT=8080` on this code-deploy app.

## 1. Local SQLite and the Azure Postgres copy

App tables used to live on **Azure Database for PostgreSQL Flexible Server**. That server is now only a **read-only source** for `backend/scripts/postgres_to_sqlite.py`.

| Item | Value |
| --- | --- |
| Host | `malstar.postgres.database.azure.com` |
| Port | `5432` |
| Copy script default database | `postgres` (falls back to `malstar` if remarks/leave tables are missing) |
| App user | `nathan` |
| TLS | `sslmode=require` |

Never commit the password, paste it into a PR, or store it in this file. URL-encode `$` as `%24` if you put it in a URL.

From a machine allowed by the Flexible Server firewall:

```powershell
cd backend
pip install "psycopg[binary]"
python scripts/postgres_to_sqlite.py --sqlite malstar.db
```

The script copies only `CustomerRemarks`, `LeavePeople`, and `LeavePlans`. Other tables are created empty (upload Dashboard / LCL / GCA later). It does not INSERT/UPDATE/DELETE on Azure Postgres.

Allow the machine that runs the copy script:

```bash
az postgres flexible-server firewall-rule create \
  --resource-group <RG> \
  --name malstar \
  --rule-name AllowCopyClient \
  --start-ip-address <YOUR_IP> \
  --end-ip-address <YOUR_IP>
```

Do not open `0.0.0.0–255.255.255.255`. Flexible Server usernames are `nathan`, not `nathan@malstar`.

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

When you are ready to run SQLite on App Service (after an explicit merge decision):

```bash
az webapp config appsettings set \
  --resource-group <RG> \
  --name MALSTAR-Toolkit \
  --settings DATABASE_PATH=/home/data/malstar.db

az webapp config appsettings delete \
  --resource-group <RG> \
  --name MALSTAR-Toolkit \
  --setting-names DATABASE_URL
```

Copy `malstar.db` onto `/home/data` first. Do not point production at a missing file.

Optional Ask LLM settings are unchanged: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`.

Oryx installs from **repo-root** `requirements.txt` and `backend/requirements.txt`. The app no longer needs `psycopg`. Install `psycopg[binary]` only on the machine that runs the copy script. GitHub Actions does not need `DATABASE_URL` at build time.

## 3. Archival copy scripts

`backend/scripts/sqlite_to_postgres.py` and `backend/scripts/live_api_to_postgres.py` wrote into Postgres. They are unused by the SQLite runtime.

## 4. Health check and scale

Portal: Monitoring → Health check → `/api/health`. That path returns 503 if the SQLite file cannot be opened.

Keep **one instance**. `/home/data` is not safe across scale-out until it is an Azure Files mount.

Keep `--workers 1 --threads 8` on F1.

Always On and custom domains are plan-SKU limits. Entra Easy Auth is unchanged.

## 5. Do not use deploy.ps1 for this app

`azure/deploy.ps1` builds a **container** named `autorating-web` and is not used for MALSTAR-Toolkit. This app is GitHub code deploy as above.
