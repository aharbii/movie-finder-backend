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
#   • The following env vars set (or edit the Variables section below):
#       ANTHROPIC_API_KEY   OPENAI_API_KEY   IMDB_API_KEY
#       IMDB_BASE_URL       QDRANT_ENDPOINT  QDRANT_API_KEY
#       APP_SECRET_KEY
#
# What this script creates:
#   Resource Group, Container Registry, Key Vault, Storage Account + File Share,
#   Log Analytics Workspace, Container Apps Environment (with Azure Files mount),
#   User-Assigned Managed Identity, Container App (first deploy), Service
#   Principal for Jenkins CI/CD.
#
# ⚠️  SQLite + Azure Files note:
#   The app uses a single SQLite file on an Azure File Share mounted at /data.
#   The Container App is capped at maxReplicas=1 to avoid multi-writer conflicts.
#   If you ever need to scale beyond 1 replica, migrate to PostgreSQL first.
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

LOCATION="eastus"                          # Azure region
SUBSCRIPTION_ID="$(az account show --query id -o tsv)"

# Resource names (globally unique names use random suffix to avoid conflicts)
SUFFIX="${ENV}"                            # e.g. "staging" or "production"
RG="rg-movie-finder-${SUFFIX}"
ACR_NAME="acrmoviefinder"                  # globally unique, no hyphens, max 50 chars
KV_NAME="kv-movie-finder-${SUFFIX}"       # globally unique, max 24 chars
STORAGE_ACCOUNT="stmoviefinder${SUFFIX}"  # globally unique, lowercase, max 24 chars
SHARE_NAME="movie-finder-db"
LOG_ANALYTICS="law-movie-finder-${SUFFIX}"
ACA_ENV_NAME="cae-movie-finder-${SUFFIX}"
ACA_STORAGE_NAME="sqlitedata"             # name within the ACA environment
ACA_APP_NAME="ca-movie-finder-${SUFFIX}"
IDENTITY_NAME="id-movie-finder-${SUFFIX}"
SP_NAME="sp-movie-finder-cicd"            # shared across envs (one SP for CI/CD)

SERVICE_NAME="movie-finder-backend"       # Docker image name in ACR

# Scaling: staging can scale to zero; production keeps 1 warm replica
if [[ "$ENV" == "production" ]]; then
    MIN_REPLICAS=1
else
    MIN_REPLICAS=0
fi

# Runtime secrets — read from environment or prompt if not set
get_secret() {
    local var_name="$1"
    local prompt_text="$2"
    local value="${!var_name:-}"
    if [[ -z "$value" ]]; then
        read -r -s -p "Enter $prompt_text: " value
        echo ""
    fi
    echo "$value"
}

ANTHROPIC_API_KEY="$(get_secret ANTHROPIC_API_KEY 'ANTHROPIC_API_KEY')"
OPENAI_API_KEY="$(get_secret OPENAI_API_KEY 'OPENAI_API_KEY')"
IMDB_API_KEY="$(get_secret IMDB_API_KEY 'IMDB_API_KEY')"
IMDB_BASE_URL="$(get_secret IMDB_BASE_URL 'IMDB_BASE_URL')"
QDRANT_ENDPOINT="$(get_secret QDRANT_ENDPOINT 'QDRANT_ENDPOINT')"
QDRANT_API_KEY="$(get_secret QDRANT_API_KEY 'QDRANT_API_KEY')"
APP_SECRET_KEY="$(get_secret APP_SECRET_KEY 'APP_SECRET_KEY (JWT signing secret)')"

echo ""
echo "Target subscription: $SUBSCRIPTION_ID"
echo "Resource group:      $RG"
echo "Location:            $LOCATION"
echo ""
read -r -p "Proceed? [y/N] " confirm
[[ "${confirm,,}" == "y" ]] || { echo "Aborted."; exit 0; }
echo ""

# --------------------------------------------------------------------------- #
# 3. Resource Group
# --------------------------------------------------------------------------- #

echo ">>> [1/11] Creating resource group..."
az group create \
    --name     "$RG" \
    --location "$LOCATION" \
    --output   none
echo "    ✓ $RG"

# --------------------------------------------------------------------------- #
# 4. Azure Container Registry
# --------------------------------------------------------------------------- #

echo ">>> [2/11] Creating Azure Container Registry..."
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
# 5. Key Vault
# --------------------------------------------------------------------------- #

echo ">>> [3/11] Creating Key Vault..."
az keyvault create \
    --name           "$KV_NAME" \
    --resource-group "$RG" \
    --location       "$LOCATION" \
    --sku            standard \
    --output         none
KV_URI="https://${KV_NAME}.vault.azure.net"
echo "    ✓ $KV_NAME ($KV_URI)"

echo "    Storing secrets..."
az keyvault secret set --vault-name "$KV_NAME" --name "APP-SECRET-KEY"    --value "$APP_SECRET_KEY"    --output none
az keyvault secret set --vault-name "$KV_NAME" --name "ANTHROPIC-API-KEY" --value "$ANTHROPIC_API_KEY" --output none
az keyvault secret set --vault-name "$KV_NAME" --name "OPENAI-API-KEY"    --value "$OPENAI_API_KEY"    --output none
az keyvault secret set --vault-name "$KV_NAME" --name "IMDB-API-KEY"      --value "$IMDB_API_KEY"      --output none
az keyvault secret set --vault-name "$KV_NAME" --name "IMDB-BASE-URL"     --value "$IMDB_BASE_URL"     --output none
az keyvault secret set --vault-name "$KV_NAME" --name "QDRANT-ENDPOINT"   --value "$QDRANT_ENDPOINT"   --output none
az keyvault secret set --vault-name "$KV_NAME" --name "QDRANT-API-KEY"    --value "$QDRANT_API_KEY"    --output none
echo "    ✓ 7 secrets stored"

# --------------------------------------------------------------------------- #
# 6. Storage Account + File Share (for SQLite persistence)
# --------------------------------------------------------------------------- #

echo ">>> [4/11] Creating Storage Account and File Share..."
az storage account create \
    --name           "$STORAGE_ACCOUNT" \
    --resource-group "$RG" \
    --location       "$LOCATION" \
    --sku            Standard_LRS \
    --kind           StorageV2 \
    --output         none

STORAGE_KEY="$(az storage account keys list \
    --account-name   "$STORAGE_ACCOUNT" \
    --resource-group "$RG" \
    --query          '[0].value' -o tsv)"

az storage share-rm create \
    --storage-account "$STORAGE_ACCOUNT" \
    --resource-group  "$RG" \
    --name            "$SHARE_NAME" \
    --quota           1 \
    --output          none
echo "    ✓ File share: $SHARE_NAME (1 GiB quota)"

# --------------------------------------------------------------------------- #
# 7. Log Analytics Workspace (required by Container Apps Environment)
# --------------------------------------------------------------------------- #

echo ">>> [5/11] Creating Log Analytics Workspace..."
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

echo ">>> [6/11] Creating Managed Identity..."
az identity create \
    --name           "$IDENTITY_NAME" \
    --resource-group "$RG" \
    --location       "$LOCATION" \
    --output         none

IDENTITY_ID="$(az identity show \
    --name           "$IDENTITY_NAME" \
    --resource-group "$RG" \
    --query          id -o tsv)"
IDENTITY_CLIENT_ID="$(az identity show \
    --name           "$IDENTITY_NAME" \
    --resource-group "$RG" \
    --query          clientId -o tsv)"
IDENTITY_PRINCIPAL_ID="$(az identity show \
    --name           "$IDENTITY_NAME" \
    --resource-group "$RG" \
    --query          principalId -o tsv)"

# Grant the identity permission to pull images from ACR
az role assignment create \
    --assignee-object-id    "$IDENTITY_PRINCIPAL_ID" \
    --assignee-principal-type ServicePrincipal \
    --role                  "AcrPull" \
    --scope                 "$ACR_ID" \
    --output                none

# Grant the identity permission to read Key Vault secrets
az keyvault set-policy \
    --name             "$KV_NAME" \
    --object-id        "$IDENTITY_PRINCIPAL_ID" \
    --secret-permissions get list \
    --output           none
echo "    ✓ $IDENTITY_NAME (AcrPull + Key Vault get/list)"

# --------------------------------------------------------------------------- #
# 9. Container Apps Environment
# --------------------------------------------------------------------------- #

echo ">>> [7/11] Creating Container Apps Environment..."
az containerapp env create \
    --name                              "$ACA_ENV_NAME" \
    --resource-group                    "$RG" \
    --location                          "$LOCATION" \
    --logs-workspace-id                 "$LAW_ID" \
    --logs-workspace-key                "$LAW_KEY" \
    --output                            none

# Attach the Azure File Share to the environment so Container Apps can mount it
az containerapp env storage set \
    --name                    "$ACA_ENV_NAME" \
    --resource-group          "$RG" \
    --storage-name            "$ACA_STORAGE_NAME" \
    --azure-file-account-name "$STORAGE_ACCOUNT" \
    --azure-file-account-key  "$STORAGE_KEY" \
    --azure-file-share-name   "$SHARE_NAME" \
    --access-mode             ReadWrite \
    --output                  none
echo "    ✓ $ACA_ENV_NAME (with Azure Files storage: $ACA_STORAGE_NAME)"

# --------------------------------------------------------------------------- #
# 10. Container App (initial provision with placeholder image)
# --------------------------------------------------------------------------- #

echo ">>> [8/11] Creating Container App..."

# Build the Container App definition as YAML so the volume mount, secrets,
# and managed identity are all configured in one atomic create call.
ACA_YAML="$(mktemp /tmp/containerapp-XXXXXX.yaml)"

cat > "$ACA_YAML" << YAML
properties:
  managedEnvironmentId: $(az containerapp env show --name "$ACA_ENV_NAME" --resource-group "$RG" --query id -o tsv)
  configuration:
    activeRevisionsMode: Single
    ingress:
      external: true
      targetPort: 8000
      transport: http
      allowInsecure: false
    registries:
    - server: ${ACR_SERVER}
      identity: ${IDENTITY_ID}
    secrets:
    - name: app-secret-key
      keyVaultUrl: ${KV_URI}/secrets/APP-SECRET-KEY
      identity: ${IDENTITY_ID}
    - name: anthropic-api-key
      keyVaultUrl: ${KV_URI}/secrets/ANTHROPIC-API-KEY
      identity: ${IDENTITY_ID}
    - name: openai-api-key
      keyVaultUrl: ${KV_URI}/secrets/OPENAI-API-KEY
      identity: ${IDENTITY_ID}
    - name: imdb-api-key
      keyVaultUrl: ${KV_URI}/secrets/IMDB-API-KEY
      identity: ${IDENTITY_ID}
    - name: imdb-base-url
      keyVaultUrl: ${KV_URI}/secrets/IMDB-BASE-URL
      identity: ${IDENTITY_ID}
    - name: qdrant-endpoint
      keyVaultUrl: ${KV_URI}/secrets/QDRANT-ENDPOINT
      identity: ${IDENTITY_ID}
    - name: qdrant-api-key
      keyVaultUrl: ${KV_URI}/secrets/QDRANT-API-KEY
      identity: ${IDENTITY_ID}
  template:
    containers:
    - name: ${SERVICE_NAME}
      # Placeholder image — Jenkins will update this on the first pipeline run
      image: mcr.microsoft.com/azuredocs/containerapps-helloworld:latest
      resources:
        cpu: 0.5
        memory: 1.0Gi
      env:
      # Non-sensitive configuration
      - name: APP_ENV
        value: ${ENV}
      - name: APP_PORT
        value: "8000"
      - name: DATABASE_URL
        value: /data/movie_finder.db
      - name: QDRANT_COLLECTION
        value: movies
      - name: EMBEDDING_MODEL
        value: text-embedding-3-large
      - name: EMBEDDING_DIMENSION
        value: "3072"
      - name: RAG_TOP_K
        value: "8"
      - name: MAX_REFINEMENTS
        value: "3"
      - name: IMDB_SEARCH_LIMIT
        value: "3"
      - name: CONFIDENCE_THRESHOLD
        value: "0.3"
      - name: LOG_LEVEL
        value: INFO
      - name: LANGSMITH_TRACING
        value: "false"
      # Sensitive — pulled from Key Vault via the managed identity at runtime
      - name: APP_SECRET_KEY
        secretRef: app-secret-key
      - name: ANTHROPIC_API_KEY
        secretRef: anthropic-api-key
      - name: OPENAI_API_KEY
        secretRef: openai-api-key
      - name: IMDB_API_KEY
        secretRef: imdb-api-key
      - name: IMDB_BASE_URL
        secretRef: imdb-base-url
      - name: QDRANT_ENDPOINT
        secretRef: qdrant-endpoint
      - name: QDRANT_API_KEY
        secretRef: qdrant-api-key
      volumeMounts:
      - volumeName: sqlite-vol
        mountPath: /data
    volumes:
    - name: sqlite-vol
      storageType: AzureFile
      storageName: ${ACA_STORAGE_NAME}
    scale:
      minReplicas: ${MIN_REPLICAS}
      # ⚠️  Hard limit: SQLite is single-writer. Do NOT raise this above 1
      # without first migrating the database to PostgreSQL.
      maxReplicas: 1
  identity:
    type: UserAssigned
    userAssignedIdentities:
      ${IDENTITY_ID}: {}
YAML

az containerapp create \
    --name           "$ACA_APP_NAME" \
    --resource-group "$RG" \
    --yaml           "$ACA_YAML" \
    --output         none

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

echo ">>> [9/11] Creating Jenkins CI/CD Service Principal..."

RG_ID="$(az group show --name "$RG" --query id -o tsv)"

# Check if SP already exists (idempotent for multi-env runs)
SP_EXISTS="$(az ad sp list --display-name "$SP_NAME" --query '[0].appId' -o tsv 2>/dev/null || true)"

if [[ -n "$SP_EXISTS" ]]; then
    echo "    Service principal '$SP_NAME' already exists (App ID: $SP_EXISTS)"
    echo "    Skipping creation — use the credentials stored from the first run."
    SP_APP_ID="$SP_EXISTS"
else
    SP_JSON="$(az ad sp create-for-rbac \
        --name        "$SP_NAME" \
        --role        "Contributor" \
        --scopes      "$RG_ID" \
        --output      json)"
    SP_APP_ID="$(echo "$SP_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['appId'])")"
    SP_PASSWORD="$(echo "$SP_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['password'])")"
    SP_TENANT="$(echo "$SP_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tenant'])")"

    # Grant AcrPush so Jenkins can push images
    az role assignment create \
        --assignee "$SP_APP_ID" \
        --role     "AcrPush" \
        --scope    "$ACR_ID" \
        --output   none

    echo ""
    echo "    ┌─────────────────────────────────────────────────────────┐"
    echo "    │  Jenkins credentials — add these now, then DELETE them  │"
    echo "    │  from your terminal history / this output               │"
    echo "    └─────────────────────────────────────────────────────────┘"
    echo ""
    echo "    Credential ID: azure-sp-app-id     Value: $SP_APP_ID"
    echo "    Credential ID: azure-sp-password   Value: $SP_PASSWORD"
    echo "    Credential ID: azure-tenant-id     Value: $SP_TENANT"
    echo "    Credential ID: azure-sub-id        Value: $SUBSCRIPTION_ID"
    echo "    Credential ID: acr-login-server    Value: $ACR_SERVER"
    echo ""
    echo "    For docker login (Username+Password credential 'azure-acr-sp'):"
    echo "      Username: $SP_APP_ID"
    echo "      Password: $SP_PASSWORD"
    echo ""
fi

# --------------------------------------------------------------------------- #
# 12. Remaining Jenkins credentials (no secrets involved)
# --------------------------------------------------------------------------- #

echo ">>> [10/11] Remaining Jenkins credentials to add..."
echo ""
echo "    Credential ID: aca-rg             Value: $RG"
echo "    Credential ID: aca-${SUFFIX}-name Value: $ACA_APP_NAME"
echo ""

# --------------------------------------------------------------------------- #
# 13. Summary
# --------------------------------------------------------------------------- #

echo ">>> [11/11] Done."
echo ""
echo "============================================="
echo " Provisioning complete: movie-finder ($ENV)"
echo "============================================="
echo ""
echo "  Container App URL : https://$APP_FQDN"
echo "  ACR               : $ACR_SERVER"
echo "  Key Vault         : $KV_URI"
echo "  SQLite mount      : /data/movie_finder.db (Azure Files)"
echo "  Resource Group    : $RG"
echo ""
echo "Next steps:"
echo "  1. Add the Jenkins credentials printed above."
echo "  2. Configure the GitHub webhook:"
echo "       GitHub repo → Settings → Webhooks → Add webhook"
echo "       Payload URL : https://<your-jenkins-host>/github-webhook/"
echo "       Content type: application/json"
echo "       Events      : Push, Pull request"
echo "  3. Push to main (or tag a release) to trigger the first real deploy."
echo "  4. Verify the app is healthy:"
echo "       curl https://$APP_FQDN/health"
echo ""
echo "⚠️  Reminder: $ACA_APP_NAME is capped at maxReplicas=1 (SQLite constraint)."
echo "   Raise this only after migrating to PostgreSQL."
echo ""
