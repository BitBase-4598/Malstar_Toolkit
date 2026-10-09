# Azure App Service settings (MALSTAR-Toolkit)

This app is a **Linux Python 3.12 Web App** deployed from **GitHub** (Oryx / `SCM_DO_BUILD_DURING_DEPLOYMENT=true`). The workflow is [`.github/workflows/main_malstar-toolkit.yml`](../.github/workflows/main_malstar-toolkit.yml).

Live site: `https://malstar-toolkit-djexgna2eghtgkep.eastasia-01.azurewebsites.net`  
Kudu / SCM: `https://malstar-toolkit-djexgna2eghtgkep.scm.eastasia-01.azurewebsites.net`

The running app uses **SQLite only**. Put the database file at `/home/data/malstar.db` and set `DATABASE_PATH` to that path. A leftover `postgresql://` `DATABASE_URL` will fail on boot.

Startup command (Configuration → General settings). Keep this exact string:

```
gunicorn --bind=0.0.0.0:8000 --chdir backend --workers 1 --threads 8 --timeout 120 app:app
```

Do not use `source`, `antenv/bin/gunicorn`, or `WEBSITES_PORT=8080` on this code-deploy app.

## 1. Application settings

Keep:

| Name | Value |
| --- | --- |
| `UPLOAD_DIR` | `/home/data/uploads` |
| `LOG_PATH` | `/home/data/malstar_toolkit.log` |
| `WEBSITES_ENABLE_APP_SERVICE_STORAGE` | `true` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |
| `FLASK_DEBUG` | `false` |
| `CORS_ORIGINS` | *(empty)* |

Set the database path and remove any Postgres URL:

| Name | Action | Value |
| --- | --- | --- |
| `DATABASE_PATH` | **Add / set** | `/home/data/malstar.db` |
| `DATABASE_URL` | **Delete** | *(must not be a `postgresql://` string)* |

Do not leave `DATABASE_URL` as a Postgres URL. The process exits if it starts with `postgres`. You can use `DATABASE_URL=sqlite:////home/data/malstar.db` instead of `DATABASE_PATH`; do not set both to different files.

Copy `malstar.db` onto `/home/data` (Kudu → File Manager) **before** the new code starts. `WEBSITES_ENABLE_APP_SERVICE_STORAGE` must stay `true` so `/home/data` persists.

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

Optional Ask LLM settings: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`.

Oryx installs from **repo-root** `requirements.txt` and `backend/requirements.txt`. GitHub Actions does not need `DATABASE_URL` at build time.

## 2. Health check and scale

Portal: Monitoring → Health check → `/api/health`. That path returns 503 if the SQLite file cannot be opened.

Keep **one instance**. `/home/data` is not safe across scale-out until it is an Azure Files mount.

Keep `--workers 1 --threads 8` on F1.

Always On and custom domains are plan-SKU limits. Entra Easy Auth is unchanged.
