#!/usr/bin/env bash
# =============================================================================
# movie-finder — Azure infrastructure provisioning script
#
# Run this ONCE per environment to create all Azure resources. After it
# completes, Jenkins handles every subsequent deployment via az containerapp
# update (no need to re-run this script on each release).
#
# Usage:
#   ./deploy/provision.sh staging
#   ./deploy/provision.sh production
#
# Prerequisites:
#   • Azure CLI installed and logged in (az login)
#   • Contributor or Owner role on the target subscription
#   • The following env vars set (or the script will prompt for them):
#       ANTHROPIC_API_KEY   OPENAI_API_KEY
#       QDRANT_ENDPOINT     QDRANT_API_KEY
#       APP_SECRET_KEY      PG_ADMIN_PASSWORD
#
# What this script creates (11 steps):
#   Resource provider registration, Resource Group, Container Registry,
#   Key Vault (6 secrets), Azure Database for PostgreSQL Flexible Server,
#   Log Analytics Workspace, Container Apps Environment,
#   User-Assigned Managed Identity (AcrPull + Key Vault),
#   Container App (first deploy), Service Principal for Jenkins CI/CD.
#
# Note on the IMDb API:
#   imdbapi.dev is a public API that requires no authentication.
#   No IMDB_API_KEY or IMDB_BASE_URL secrets are needed.
# =============================================================================

set -euo pipefail

# --------------------------------------------------------------------------- #
# 1. Arguments & environment check
# --------------------------------------------------------------------------- #

ENV="${1:-}"
if [[ "$ENV" != "staging" && "$ENV" != "production" ]]; then
    echo "Usage: $0 <staging|production>"
    exit 1
fi

# Verify the user is logged in to Azure
if ! az account show &>/dev/null; then
    echo "Not logged in to Azure. Run: az login"
    exit 1
fi

echo ""
echo "============================================="
echo " Provisioning: movie-finder ($ENV)"
echo "============================================="
echo ""

# --------------------------------------------------------------------------- #
# 2. Variables — edit these to match your Azure environment
# --------------------------------------------------------------------------- #

LOCATION="uaenorth"                        # Azure region (UAE North — closest to Egypt)
SUBSCRIPTION_ID="$(az account show --query id -o tsv)"

# Resource names (globally unique names use random suffix to avoid conflicts)
SUFFIX="${ENV}"                            # e.g. "staging" or "production"
RG="rg-movie-finder-${SUFFIX}"
ACR_NAME="acrmoviefinder"                  # globally unique, no hyphens, max 50 chars
KV_NAME="kv-movie-finder-${SUFFIX}"       # globally unique, max 24 chars
PG_SERVER="pg-movie-finder-${SUFFIX}"     # globally unique, max 63 chars
PG_DB="movie_finder"
PG_ADMIN_USER="pgadmin"
LOG_ANALYTICS="law-movie-finder-${SUFFIX}"
ACA_ENV_NAME="cae-movie-finder-${SUFFIX}"
ACA_APP_NAME="ca-movie-finder-${SUFFIX}"
IDENTITY_NAME="id-movie-finder-${SUFFIX}"
SP_NAME="sp-movie-finder-cicd"            # shared across envs (one SP for CI/CD)

SERVICE_NAME="movie-finder-backend"       # Docker image name in ACR

# Scaling — staging can scale to zero; production keeps 1 warm replica
# PostgreSQL supports concurrent connections so maxReplicas > 1 is safe.
if [[ "$ENV" == "production" ]]; then
    MIN_REPLICAS=1
    MAX_REPLICAS=4
    PG_SKU="Standard_B2ms"
else
    MIN_REPLICAS=0
    MAX_REPLICAS=2
    PG_SKU="Standard_B1ms"
fi

# Runtime secrets — read from environment or prompt if not set.
# Prompt and post-input newline go to /dev/tty so they reach the terminal
# even when this function is called inside a command-substitution expression.
get_secret() {
    local var_name="$1"
    local prompt_text="$2"
    local value="${!var_name:-}"
    if [[ -z "$value" ]]; then
        read -r -s -p $'\n'"Enter $prompt_text: " value </dev/tty
        echo "" >/dev/tty
    fi
    echo "$value"
}

ANTHROPIC_API_KEY="$(get_secret ANTHROPIC_API_KEY 'ANTHROPIC_API_KEY')"
OPENAI_API_KEY="$(get_secret OPENAI_API_KEY 'OPENAI_API_KEY')"
QDRANT_ENDPOINT="$(get_secret QDRANT_ENDPOINT 'QDRANT_ENDPOINT')"
QDRANT_API_KEY="$(get_secret QDRANT_API_KEY 'QDRANT_API_KEY')"
APP_SECRET_KEY="$(get_secret APP_SECRET_KEY 'APP_SECRET_KEY (JWT signing secret)')"
PG_ADMIN_PASSWORD="$(get_secret PG_ADMIN_PASSWORD 'PostgreSQL admin password (min 8 chars, must contain upper+lower+digit+symbol)')"

echo ""
echo "Target subscription: $SUBSCRIPTION_ID"
echo "Resource group:      $RG"
echo "Location:            $LOCATION"
echo ""
read -r -p "Proceed? [y/N] " confirm
[[ "${confirm,,}" == "y" ]] || { echo "Aborted."; exit 0; }
echo ""

# --------------------------------------------------------------------------- #
# 3. Azure resource provider registration
# --------------------------------------------------------------------------- #

echo ">>> [1/11] Registering Azure resource providers..."
_register_provider() {
    local ns="$1"
    local state
    state="$(az provider show --namespace "$ns" --query registrationState -o tsv 2>/dev/null || echo "NotRegistered")"
    if [[ "$state" != "Registered" ]]; then
        echo "    Registering $ns (waiting for activation)..."
        az provider register --namespace "$ns" --wait --output none
    fi
    echo "    ✓ $ns"
}
_register_provider Microsoft.ContainerRegistry
_register_provider Microsoft.KeyVault
_register_provider Microsoft.DBforPostgreSQL
_register_provider Microsoft.OperationalInsights
_register_provider Microsoft.App
_register_provider Microsoft.ManagedIdentity

# --------------------------------------------------------------------------- #
# 4. Resource Group
# --------------------------------------------------------------------------- #

echo ">>> [2/11] Creating resource group..."
az group create \
    --name     "$RG" \
    --location "$LOCATION" \
    --output   none
echo "    ✓ $RG"

# --------------------------------------------------------------------------- #
# 5. Azure Container Registry
# --------------------------------------------------------------------------- #

echo ">>> [3/11] Creating Azure Container Registry..."
az acr create \
    --name           "$ACR_NAME" \
    --resource-group "$RG" \
    --sku            Basic \
    --admin-enabled  false \
    --output         none
ACR_SERVER="${ACR_NAME}.azurecr.io"
ACR_ID="$(az acr show --name "$ACR_NAME" --resource-group "$RG" --query id -o tsv)"
echo "    ✓ $ACR_SERVER"

# --------------------------------------------------------------------------- #
# 5. Key Vault  (DATABASE_URL stored after PostgreSQL is provisioned below)
# --------------------------------------------------------------------------- #

echo ">>> [4/11] Creating Key Vault..."
if ! az keyvault show --name "$KV_NAME" --resource-group "$RG" --output none 2>/dev/null; then
    az keyvault create \
        --name           "$KV_NAME" \
        --resource-group "$RG" \
        --location       "$LOCATION" \
        --sku            standard \
        --output         none
fi
KV_URI="https://${KV_NAME}.vault.azure.net"
KV_ID="$(az keyvault show --name "$KV_NAME" --resource-group "$RG" --query id -o tsv)"
echo "    ✓ $KV_NAME ($KV_URI)"

# Key Vault uses Azure RBAC by default — the creator has no automatic secret
# access. Grant "Key Vault Secrets Officer" to the current CLI user, then wait
# for RBAC propagation before writing secrets.
echo "    Granting Key Vault Secrets Officer to current user..."
CURRENT_USER_OID="$(az ad signed-in-user show --query id -o tsv)"
az role assignment create \
    --assignee-object-id      "$CURRENT_USER_OID" \
    --assignee-principal-type User \
    --role                    "Key Vault Secrets Officer" \
    --scope                   "$KV_ID" \
    --output                  none 2>/dev/null || true
echo "    Waiting 30 s for RBAC propagation..."
sleep 30

echo "    Storing secrets..."
az keyvault secret set --vault-name "$KV_NAME" --name "APP-SECRET-KEY"    --value "$APP_SECRET_KEY"    --output none
az keyvault secret set --vault-name "$KV_NAME" --name "ANTHROPIC-API-KEY" --value "$ANTHROPIC_API_KEY" --output none
az keyvault secret set --vault-name "$KV_NAME" --name "OPENAI-API-KEY"    --value "$OPENAI_API_KEY"    --output none
az keyvault secret set --vault-name "$KV_NAME" --name "QDRANT-ENDPOINT"   --value "$QDRANT_ENDPOINT"   --output none
az keyvault secret set --vault-name "$KV_NAME" --name "QDRANT-API-KEY"    --value "$QDRANT_API_KEY"    --output none
echo "    ✓ 5 secrets stored (DATABASE-URL will be added after PostgreSQL is ready)"

# --------------------------------------------------------------------------- #
# 6. Azure Database for PostgreSQL Flexible Server
# --------------------------------------------------------------------------- #

echo ">>> [5/11] Creating Azure Database for PostgreSQL Flexible Server..."
echo "    SKU: $PG_SKU  (Burstable tier — adjust in Variables section for higher load)"

if ! az postgres flexible-server show --name "$PG_SERVER" --resource-group "$RG" --output none 2>/dev/null; then
    az postgres flexible-server create \
        --name            "$PG_SERVER" \
        --resource-group  "$RG" \
        --location        "$LOCATION" \
        --admin-user      "$PG_ADMIN_USER" \
        --admin-password  "$PG_ADMIN_PASSWORD" \
        --sku-name        "$PG_SKU" \
        --tier            Burstable \
        --version         16 \
        --storage-size    32 \
        --public-access   0.0.0.0 \
        --output          none
    # --public-access 0.0.0.0 creates the "Allow access to Azure services" firewall
    # rule, which permits Container Apps to connect to the server.
fi

# Create the application database (idempotent — skipped if it already exists)
az postgres flexible-server db create \
    --server-name    "$PG_SERVER" \
    --resource-group "$RG" \
    --database-name  "$PG_DB" \
    --output         none 2>/dev/null || true

PG_FQDN="${PG_SERVER}.postgres.database.azure.com"
DATABASE_URL="postgresql://${PG_ADMIN_USER}:${PG_ADMIN_PASSWORD}@${PG_FQDN}/${PG_DB}?sslmode=require"

az keyvault secret set --vault-name "$KV_NAME" --name "DATABASE-URL" --value "$DATABASE_URL" --output none
echo "    ✓ $PG_SERVER ($PG_FQDN)"
echo "    ✓ Database: $PG_DB"
echo "    ✓ DATABASE-URL stored in Key Vault"

# --------------------------------------------------------------------------- #
# 7. Log Analytics Workspace (required by Container Apps Environment)
# --------------------------------------------------------------------------- #

echo ">>> [6/11] Creating Log Analytics Workspace..."
az monitor log-analytics workspace create \
    --workspace-name "$LOG_ANALYTICS" \
    --resource-group "$RG" \
    --location       "$LOCATION" \
    --output         none

LAW_ID="$(az monitor log-analytics workspace show \
    --workspace-name "$LOG_ANALYTICS" \
    --resource-group "$RG" \
    --query          customerId -o tsv)"
LAW_KEY="$(az monitor log-analytics workspace get-shared-keys \
    --workspace-name "$LOG_ANALYTICS" \
    --resource-group "$RG" \
    --query          primarySharedKey -o tsv)"
echo "    ✓ $LOG_ANALYTICS"

# --------------------------------------------------------------------------- #
# 8. User-Assigned Managed Identity
# --------------------------------------------------------------------------- #

echo ">>> [7/11] Creating Managed Identity..."
az identity create \
    --name           "$IDENTITY_NAME" \
    --resource-group "$RG" \
    --location       "$LOCATION" \
    --output         none

# Force canonical camelCase on the resource ID. The Azure CLI often returns
# "resourcegroups" (all-lowercase) but the Container Apps ARM validator does
# a case-sensitive match and requires "resourceGroups".
IDENTITY_ID="$(az identity show \
    --name           "$IDENTITY_NAME" \
    --resource-group "$RG" \
    --query          id -o tsv | sed 's/resourcegroups/resourceGroups/gi')"
IDENTITY_CLIENT_ID="$(az identity show \
    --name           "$IDENTITY_NAME" \
    --resource-group "$RG" \
    --query          clientId -o tsv)"
IDENTITY_PRINCIPAL_ID="$(az identity show \
    --name           "$IDENTITY_NAME" \
    --resource-group "$RG" \
    --query          principalId -o tsv)"

# Pull images from ACR
az role assignment create \
    --assignee-object-id      "$IDENTITY_PRINCIPAL_ID" \
    --assignee-principal-type ServicePrincipal \
    --role                    "AcrPull" \
    --scope                   "$ACR_ID" \
    --output                  none 2>/dev/null || true

# Read secrets from Key Vault — vault uses RBAC authorization, so grant the
# "Key Vault Secrets User" role rather than using access policies.
az role assignment create \
    --assignee-object-id      "$IDENTITY_PRINCIPAL_ID" \
    --assignee-principal-type ServicePrincipal \
    --role                    "Key Vault Secrets User" \
    --scope                   "$KV_ID" \
    --output                  none 2>/dev/null || true

echo "    ✓ $IDENTITY_NAME (AcrPull + Key Vault Secrets User)"

# Poll until the AcrPull assignment is visible in the ARM API before
# creating the Container App. A fixed sleep is not reliable across regions.
echo "    Waiting for AcrPull role assignment to propagate..."
for _i in $(seq 1 36); do
    _found="$(az role assignment list \
        --assignee   "$IDENTITY_PRINCIPAL_ID" \
        --role       "AcrPull" \
        --scope      "$ACR_ID" \
        --query      '[0].id' -o tsv 2>/dev/null || true)"
    if [[ -n "$_found" ]]; then
        echo "    ✓ AcrPull confirmed (after $((_i * 5)) s)"
        break
    fi
    sleep 5
done

# --------------------------------------------------------------------------- #
# 9. Container Apps Environment
# --------------------------------------------------------------------------- #

echo ">>> [8/11] Creating Container Apps Environment..."
az containerapp env create \
    --name                              "$ACA_ENV_NAME" \
    --resource-group                    "$RG" \
    --location                          "$LOCATION" \
    --logs-workspace-id                 "$LAW_ID" \
    --logs-workspace-key                "$LAW_KEY" \
    --output                            none
echo "    ✓ $ACA_ENV_NAME"

# --------------------------------------------------------------------------- #
# 10. Container App (initial provision with placeholder image)
# --------------------------------------------------------------------------- #

echo ">>> [9/11] Creating Container App..."

ACA_ENV_ID="$(az containerapp env show \
    --name           "$ACA_ENV_NAME" \
    --resource-group "$RG" \
    --query          id -o tsv)"

ACA_YAML="$(mktemp /tmp/containerapp-XXXXXX.yaml)"

# Minimal skeleton — public placeholder image, no identity references.
# The ARM validator rejects identity references until propagation is complete.
# Jenkins configures secrets, registry, managed identity, and the real image
# on the first pipeline run via az containerapp update --yaml.
cat > "$ACA_YAML" << YAML
properties:
  managedEnvironmentId: ${ACA_ENV_ID}
  configuration:
    activeRevisionsMode: Single
    ingress:
      external: true
      targetPort: 8000
      transport: http
      allowInsecure: false
  template:
    containers:
    - name: ${SERVICE_NAME}
      image: mcr.microsoft.com/azuredocs/containerapps-helloworld:latest
      resources:
        cpu: 0.5
        memory: 1.0Gi
      env:
      - name: APP_ENV
        value: ${ENV}
      - name: APP_PORT
        value: "8000"
      - name: LOG_LEVEL
        value: INFO
    scale:
      minReplicas: ${MIN_REPLICAS}
      maxReplicas: ${MAX_REPLICAS}
YAML

if az containerapp show --name "$ACA_APP_NAME" --resource-group "$RG" --output none 2>/dev/null; then
    # App already exists (e.g. from a failed previous run) — update it instead
    az containerapp update \
        --name           "$ACA_APP_NAME" \
        --resource-group "$RG" \
        --yaml           "$ACA_YAML" \
        --output         none
else
    az containerapp create \
        --name           "$ACA_APP_NAME" \
        --resource-group "$RG" \
        --yaml           "$ACA_YAML" \
        --output         none
fi

rm -f "$ACA_YAML"

APP_FQDN="$(az containerapp show \
    --name           "$ACA_APP_NAME" \
    --resource-group "$RG" \
    --query          'properties.configuration.ingress.fqdn' -o tsv)"
echo "    ✓ $ACA_APP_NAME"
echo "    URL: https://$APP_FQDN"

# --------------------------------------------------------------------------- #
# 11. Service Principal for Jenkins CI/CD
# --------------------------------------------------------------------------- #

echo ">>> [10/11] Creating Jenkins CI/CD Service Principal..."

RG_ID="$(az group show --name "$RG" --query id -o tsv)"

# Idempotent — skip creation if the SP already exists (e.g. second env run)
SP_EXISTS="$(az ad sp list --display-name "$SP_NAME" --query '[0].appId' -o tsv 2>/dev/null || true)"

if [[ -n "$SP_EXISTS" ]]; then
    echo "    Service principal '$SP_NAME' already exists (App ID: $SP_EXISTS)"
    echo "    Granting Contributor on new resource group..."
    az role assignment create \
        --assignee "$SP_EXISTS" \
        --role     "Contributor" \
        --scope    "$RG_ID" \
        --output   none
    echo "    Use the credentials stored from the first run."
    SP_APP_ID="$SP_EXISTS"
else
    SP_JSON="$(az ad sp create-for-rbac \
        --name        "$SP_NAME" \
        --role        "Contributor" \
        --scopes      "$RG_ID" \
        --output      json)"
    SP_APP_ID="$(echo  "$SP_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['appId'])")"
    SP_PASSWORD="$(echo "$SP_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['password'])")"
    SP_TENANT="$(echo  "$SP_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tenant'])")"

    # Grant AcrPush so Jenkins can push images
    az role assignment create \
        --assignee "$SP_APP_ID" \
        --role     "AcrPush" \
        --scope    "$ACR_ID" \
        --output   none

    echo ""
    echo "    ┌───────────────────────────────────────────────────────────────────┐"
    echo "    │   Jenkins credentials — add these NOW, then clear terminal history │"
    echo "    └───────────────────────────────────────────────────────────────────┘"
    echo ""
    echo "    ── Shared with frontend pipeline (create once) ──────────────────────"
    echo ""
    echo "    ID: acr-login-server        Type: Secret Text"
    echo "        Value: $ACR_SERVER"
    echo ""
    echo "    ID: acr-credentials         Type: Username + Password"
    echo "        Username: $SP_APP_ID"
    echo "        Password: $SP_PASSWORD"
    echo ""
    echo "    ID: azure-sp                Type: Username + Password"
    echo "        Username: $SP_APP_ID"
    echo "        Password: $SP_PASSWORD"
    echo ""
    echo "    ── Backend-specific ─────────────────────────────────────────────────"
    echo ""
    echo "    ID: azure-tenant-id         Type: Secret Text"
    echo "        Value: $SP_TENANT"
    echo ""
    echo "    ID: azure-sub-id            Type: Secret Text"
    echo "        Value: $SUBSCRIPTION_ID"
    echo ""
fi

# --------------------------------------------------------------------------- #
# 12. Remaining Jenkins credentials (resource names, no secrets)
# --------------------------------------------------------------------------- #

echo ">>> [11/11] Additional Jenkins credentials to add..."
echo ""
echo "    ID: aca-rg                  Type: Secret Text"
echo "        Value: $RG"
echo ""
echo "    ID: aca-${SUFFIX}-name      Type: Secret Text"
echo "        Value: $ACA_APP_NAME"
echo ""

# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #

echo "============================================="
echo " Provisioning complete: movie-finder ($ENV)"
echo "============================================="
echo ""
echo "  Container App URL  : https://$APP_FQDN"
echo "  ACR                : $ACR_SERVER"
echo "  Key Vault          : $KV_URI"
echo "  PostgreSQL server  : $PG_FQDN"
echo "  PostgreSQL database: $PG_DB"
echo "  Resource Group     : $RG"
echo ""
echo "Next steps:"
echo "  1. Add the Jenkins credentials printed above."
echo "  2. If provisioning a second environment, run this script again."
echo "     The SP '$SP_NAME' will be reused and granted Contributor on the new RG."
echo "  3. Configure the GitHub webhook:"
echo "       GitHub repo → Settings → Webhooks → Add webhook"
echo "       Payload URL : https://<your-ngrok-host>/github-webhook/"
echo "       Content type: application/json"
echo "       Events      : Push, Pull request"
echo "  4. Push to main (or tag a release) to trigger the first real deploy."
echo "  5. Verify the app is healthy after the first Jenkins build:"
echo "       curl https://$APP_FQDN/health"
echo ""
