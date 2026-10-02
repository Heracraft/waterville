#!/usr/bin/env bash
# Deploy (or update) the Waterville City Code assistant to Azure.
#
# Needs: az, docker, jq, and a service principal with Contributor plus
# "Role Based Access Control Administrator" on the resource group:
#   AZURE_CLIENT_ID AZURE_CLIENT_SECRET AZURE_TENANT_ID AZURE_SUBSCRIPTION_ID
#
# Optional:
#   RESOURCE_GROUP     default rg-waterville-rag (must exist; its region is used)
#   CHAT_MODEL         chat model name; default: first of gpt-5-mini, gpt-4.1-mini,
#                      gpt-4o-mini with quota in the region
#   CHAT_MODEL_VERSION default: newest GA version in the region
#   CHAT_CAPACITY      thousands of tokens/minute for the chat model (default 50)
#   EMBEDDING_CAPACITY thousands of tokens/minute for embeddings (default 150)
#   MIN_REPLICAS       0 scales to zero when idle (default), 1 avoids cold starts
#   REFRESH=1          run the refresh job even if this is not the first deploy
set -euo pipefail
cd "$(dirname "$0")/.."

RG=${RESOURCE_GROUP:-rg-waterville-rag}
CHAT_CAPACITY=${CHAT_CAPACITY:-50}
EMBEDDING_CAPACITY=${EMBEDDING_CAPACITY:-150}
MIN_REPLICAS=${MIN_REPLICAS:-0}
EMBEDDING_MODEL=text-embedding-3-large

log() { printf '\n==> %s\n' "$*" >&2; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

for v in AZURE_CLIENT_ID AZURE_CLIENT_SECRET AZURE_TENANT_ID AZURE_SUBSCRIPTION_ID; do
  [ -n "${!v:-}" ] || die "$v is not set"
done

export AZURE_CORE_ONLY_SHOW_ERRORS=1 AZURE_EXTENSION_USE_DYNAMIC_INSTALL=yes_without_prompt
log "Signing in as service principal"
az login --service-principal -u "$AZURE_CLIENT_ID" -p "$AZURE_CLIENT_SECRET" --tenant "$AZURE_TENANT_ID" -o none
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

LOCATION=$(az group show -n "$RG" --query location -o tsv) || die "resource group $RG not found or not accessible"
log "Resource group $RG in $LOCATION"

for ns in Microsoft.Search Microsoft.CognitiveServices Microsoft.App Microsoft.ContainerRegistry \
          Microsoft.OperationalInsights Microsoft.ManagedIdentity; do
  state=$(az provider show -n "$ns" --query registrationState -o tsv 2>/dev/null || echo Unknown)
  [ "$state" = Registered ] || die "provider $ns is $state; run: az provider register --namespace $ns"
done

# ------------------------------------------------------------------ models
log "Checking model availability and quota in $LOCATION"
MODELS=$(az cognitiveservices model list -l "$LOCATION" -o json)
USAGE=$(az cognitiveservices usage list -l "$LOCATION" -o json)

# pick_model NAME CAPACITY -> "version sku" or nothing
pick_model() {
  local name=$1 cap=$2 want_version=${3:-}
  for sku in GlobalStandard Standard; do
    local ver
    ver=$(jq -r --arg n "$name" --arg s "$sku" --arg v "$want_version" '
      [ .[] | select(.kind == "OpenAI" and .model.name == $n)
            | select(any(.model.skus[]?; .name == $s))
            | select(.model.lifecycleStatus != "Deprecated" and .model.lifecycleStatus != "Deprecating")
            | select($v == "" or .model.version == $v)
            | .model.version ] | sort | last // empty' <<<"$MODELS")
    [ -n "$ver" ] || continue
    local free
    free=$(jq -r --arg k "OpenAI.$sku.$name" '
      [ .[] | select(.name.value == $k) | (.limit - .currentValue) ] | first // 0' <<<"$USAGE")
    if [ "${free%.*}" -ge "$cap" ]; then echo "$ver $sku"; return; fi
    printf '  %s %s: only %s quota free, need %s\n' "$name" "$sku" "$free" "$cap" >&2
  done
}

CHAT_SKU="" CHAT_VERSION=""
for m in ${CHAT_MODEL:-gpt-5-mini gpt-4.1-mini gpt-4o-mini}; do
  if r=$(pick_model "$m" "$CHAT_CAPACITY" "${CHAT_MODEL_VERSION:-}") && [ -n "$r" ]; then
    CHAT_MODEL=$m; read -r CHAT_VERSION CHAT_SKU <<<"$r"; break
  fi
done
[ -n "$CHAT_SKU" ] || die "no chat model with ${CHAT_CAPACITY}K TPM quota in $LOCATION; request quota or set CHAT_MODEL / CHAT_CAPACITY"

r=$(pick_model "$EMBEDDING_MODEL" "$EMBEDDING_CAPACITY") || true
[ -n "$r" ] || die "no $EMBEDDING_MODEL quota (${EMBEDDING_CAPACITY}K TPM) in $LOCATION; lower EMBEDDING_CAPACITY or request quota"
read -r EMBEDDING_VERSION EMBEDDING_SKU <<<"$r"

REASONING=""
[[ $CHAT_MODEL =~ ^(gpt-5|o[0-9]) ]] && REASONING=low
log "Chat: $CHAT_MODEL $CHAT_VERSION ($CHAT_SKU, ${CHAT_CAPACITY}K TPM${REASONING:+, reasoning=$REASONING})"
log "Embeddings: $EMBEDDING_MODEL $EMBEDDING_VERSION ($EMBEDDING_SKU, ${EMBEDDING_CAPACITY}K TPM)"

PARAMS=(
  chatModel="$CHAT_MODEL" chatModelVersion="$CHAT_VERSION" chatSku="$CHAT_SKU"
  chatCapacity="$CHAT_CAPACITY" chatReasoningEffort="$REASONING"
  embeddingModel="$EMBEDDING_MODEL" embeddingModelVersion="$EMBEDDING_VERSION"
  embeddingSku="$EMBEDDING_SKU" embeddingCapacity="$EMBEDDING_CAPACITY"
  minReplicas="$MIN_REPLICAS"
)

# ------------------------------------------------------------------ infra pass 1
FIRST_DEPLOY=0
az containerapp show -g "$RG" -n waterville-app -o none 2>/dev/null || FIRST_DEPLOY=1

log "Deploying core resources (Search, OpenAI, registry, identities)"
OUT=$(az deployment group create -g "$RG" -n core -f infra/main.bicep \
  -p "${PARAMS[@]}" deployApps=false --query properties.outputs -o json)
ACR_NAME=$(jq -r .acrName.value <<<"$OUT")
ACR_SERVER=$(jq -r .acrLoginServer.value <<<"$OUT")

# ------------------------------------------------------------------ image
TAG=$(git rev-parse --short HEAD)
git diff --quiet HEAD -- ecode app infra Dockerfile pyproject.toml uv.lock || TAG="$TAG-dirty-$(date +%s)"
IMAGE="$ACR_SERVER/waterville:$TAG"
log "Building and pushing $IMAGE"
docker build -t "$IMAGE" .
az acr login -n "$ACR_NAME"
docker push "$IMAGE"

# ------------------------------------------------------------------ infra pass 2
log "Deploying app and refresh job"
OUT=$(az deployment group create -g "$RG" -n apps -f infra/main.bicep \
  -p "${PARAMS[@]}" deployApps=true image="$IMAGE" --query properties.outputs -o json)
APP_URL=$(jq -r .appUrl.value <<<"$OUT")
JOB=$(jq -r .jobName.value <<<"$OUT")

# ------------------------------------------------------------------ load index
if [ "$FIRST_DEPLOY" = 1 ] || [ "${REFRESH:-0}" = 1 ]; then
  if [ "$FIRST_DEPLOY" = 1 ]; then
    log "Waiting 2 minutes for new role assignments to propagate"
    sleep 120
  fi
  log "Running the refresh job to crawl eCode360 and load the index (about 10 minutes)"
  EXEC=$(az containerapp job start -g "$RG" -n "$JOB" --query name -o tsv)
  while :; do
    STATUS=$(az containerapp job execution show -g "$RG" -n "$JOB" --job-execution-name "$EXEC" \
      --query properties.status -o tsv)
    case "$STATUS" in
      Succeeded) log "Index loaded"; break ;;
      Failed|Stopped|Degraded)
        die "refresh job $EXEC ended as $STATUS; logs: az containerapp job logs show -g $RG -n $JOB --execution $EXEC --container refresh" ;;
    esac
    sleep 20
  done
fi

# ------------------------------------------------------------------ smoke test
log "Smoke test against $APP_URL"
for _ in $(seq 1 30); do
  curl -fsS "$APP_URL/healthz" >/dev/null 2>&1 && break
  sleep 5
done
ANSWER=$(curl -fsS -N --max-time 120 "$APP_URL/api/chat" -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"What is the fee for a short-term rental license?"}]}' \
  | sed -n 's/^data: //p' | jq -rj 'objects | select(.text) | .text')
[ -n "$ANSWER" ] || die "smoke test returned no answer"
printf '%s\n' "$ANSWER" | head -20

log "Done: $APP_URL"
