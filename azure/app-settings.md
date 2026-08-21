# Azure App Service settings

Use a **Linux** Web App with a **custom container**. Push the image to Azure Container Registry (or Docker Hub), then point the Web App at that image.

From a machine logged in with Azure CLI, you can run [`deploy.ps1`](deploy.ps1):

```powershell
.\azure\deploy.ps1
```

## Required application settings

| Name | Value | Why |
|------|--------|-----|
| `WEBSITES_PORT` | `8080` | Tells App Service which container port to route to |
| `WEBSITES_ENABLE_APP_SERVICE_STORAGE` | `true` | Persists `/home` across restarts |
| `DATABASE_PATH` | `/home/data/customer_remark.db` | SQLite file on persistent `/home` |
| `UPLOAD_DIR` | `/home/data/uploads` | File/SOP uploads on persistent `/home` |
| `PORT` | `8080` | Gunicorn bind port inside the container |
| `FLASK_DEBUG` | `false` | Never enable debug in Azure |
| `CORS_ORIGINS` | *(empty)* | Same-origin; Flask serves the SPA |

Optional:

| Name | Value | Why |
| --- | --- | --- |
| `MAX_UPLOAD_MB` | `5` | CSV / file upload cap |
| `STATIC_DIR` | `/app/frontend/dist` | Already set in the image |
| `AZURE_OPENAI_ENDPOINT` | `https://YOUR-RESOURCE.openai.azure.com` | Enables generated Ask answers. Leave empty for keyword-only retrieval |
| `AZURE_OPENAI_API_KEY` | *(secret)* | Azure OpenAI key. Do not put this in the frontend |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | `gpt-4o-mini` | Chat deployment name (not the model catalog name) |
| `AZURE_OPENAI_API_VERSION` | `2024-06-01` | Optional. Defaults to `2024-06-01` |

Ask works without Azure OpenAI: it searches SOP steps and uploaded DOCX/Excel text (SQLite FTS5) and returns cited excerpts. When the three `AZURE_OPENAI_*` settings above are set, `/api/ask` sends those excerpts to the chat deployment and returns a generated answer plus the same citations.

`AZURE_OPENAI_EMBED_DEPLOYMENT` is not used in this version.

## Health check

In the Azure Portal: **Monitoring → Health check** → path `/api/health`.

## Persist SQLite (required)

App Service container disks are ephemeral unless you persist `/home`.

1. Enable `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true`.
2. Recommended extra step: **Configuration → Path mappings → Azure Storage**
   - Mount an Azure Files share at `/home/data`
   - This survives scale-out, swap, and some storage resets that `/home` alone may not

Do **not** scale out to more than one instance while using SQLite. Use a single instance.

## Deploy from Azure CLI

```bash
az group create --name rg-autorating --location eastasia

az acr create --resource-group rg-autorating --name autoratingacr --sku Basic --admin-enabled true

az acr build --registry autoratingacr --image autoratingweb:latest .

az appservice plan create --name plan-autorating --resource-group rg-autorating --is-linux --sku B1

az webapp create --resource-group rg-autorating --plan plan-autorating --name autorating-web --deployment-container-image-name autoratingacr.azurecr.io/autoratingweb:latest

az webapp config appsettings set --resource-group rg-autorating --name autorating-web --settings WEBSITES_PORT=8080 WEBSITES_ENABLE_APP_SERVICE_STORAGE=true DATABASE_PATH=/home/data/customer_remark.db UPLOAD_DIR=/home/data/uploads PORT=8080 FLASK_DEBUG=false CORS_ORIGINS=

az webapp config container set --name autorating-web --resource-group rg-autorating --enable-app-service-storage true
```

Give the Web App permission to pull from ACR (`AcrPull` on the registry, or enable admin credentials for a first deploy).

## Security note

There is no in-app login. Before exposing the site, enable **Easy Auth** (Microsoft Entra ID), restrict by IP / VNet, or put the app behind a private endpoint.
