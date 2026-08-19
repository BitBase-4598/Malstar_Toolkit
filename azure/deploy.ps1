param(
    [string]$ResourceGroup = "rg-autorating",
    [string]$Location = "eastasia",
    [string]$AcrName = "autoratingacr",
    [string]$PlanName = "plan-autorating",
    [string]$WebAppName = "autorating-web",
    [string]$ImageName = "autoratingweb:latest",
    [string]$Sku = "B1"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI (az) is required. Install it and run az login first."
}

$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    throw "Not logged in. Run az login, then run this script again."
}

Write-Host "Using subscription: $($account.name) ($($account.id))"
Set-Location $RepoRoot

az group create --name $ResourceGroup --location $Location | Out-Null
az acr create --resource-group $ResourceGroup --name $AcrName --sku Basic --admin-enabled true | Out-Null

Write-Host "Building image $ImageName in ACR $AcrName..."
az acr build --registry $AcrName --image $ImageName .

$image = "$AcrName.azurecr.io/$ImageName"
az appservice plan create --name $PlanName --resource-group $ResourceGroup --is-linux --sku $Sku | Out-Null

$existing = az webapp show --resource-group $ResourceGroup --name $WebAppName 2>$null
if (-not $existing) {
    az webapp create `
        --resource-group $ResourceGroup `
        --plan $PlanName `
        --name $WebAppName `
        --deployment-container-image-name $image | Out-Null
}

az webapp config appsettings set `
    --resource-group $ResourceGroup `
    --name $WebAppName `
    --settings `
        WEBSITES_PORT=8080 `
        WEBSITES_ENABLE_APP_SERVICE_STORAGE=true `
        DATABASE_PATH=/home/data/customer_remark.db `
        PORT=8080 `
        FLASK_DEBUG=false `
        CORS_ORIGINS= | Out-Null

az webapp config container set `
    --name $WebAppName `
    --resource-group $ResourceGroup `
    --docker-custom-image-name $image `
    --docker-registry-server-url "https://$AcrName.azurecr.io" `
    --enable-app-service-storage true | Out-Null

az webapp update --resource-group $ResourceGroup --name $WebAppName --set siteConfig.healthCheckPath="/api/health" | Out-Null

$url = "https://$WebAppName.azurewebsites.net"
Write-Host "Deployed. Open $url"
Write-Host "Keep the app at a single instance while using SQLite."
