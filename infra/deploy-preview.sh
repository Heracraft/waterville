#!/usr/bin/env bash
# Deploy (or update) the preview of the Waterville City Code assistant: the
# staff desk and the public tools, next to production, in the same Container
# Apps environment. See docs/preview.md.
#
#   infra/deploy-preview.sh            build, push, deploy, refresh if needed, smoke test
#   infra/deploy-preview.sh --what-if  show what a deploy would change, change nothing
#
# The preview gets its own container app (waterville-preview), manual refresh
# job (waterville-preview-refresh), identities, storage account and search
# index (waterville-code-preview). It reuses the existing environment,
# registry, AI Search service, Azure OpenAI account and Log Analytics
# workspace without changing them. This script deploys only infra/preview.bicep;
# it never deploys infra/main.bicep and never updates waterville-app or
# waterville-refresh. Before deploying it runs a what-if and stops if any
# existing resource would change, and afterwards it checks that production
# still runs the same revision and image.
#
# Needs: az, docker (unless IMAGE is set), jq, curl, uv, and the service
# principal used by infra/deploy.sh (Contributor plus "Role Based Access
# Control Administrator" on the resource group):
#   AZURE_CLIENT_ID AZURE_CLIENT_SECRET AZURE_TENANT_ID AZURE_SUBSCRIPTION_ID
#
# Optional:
#   RESOURCE_GROUP       default rg-waterville-rag
#   IMAGE                deploy this image instead of building one
#   STAFF_USERS          JSON {"name": "scrypt$..."} (python -m app.auth hash NAME).
#                        Unset: reuse the saved value, else create one demo
#                        account "inspector" and write its password to
#                        PREVIEW_CREDENTIALS
#   SESSION_SECRET       cookie signing key. Unset: reuse the saved one, else generate
#   PREVIEW_CREDENTIALS  default ~/waterville-preview-credentials.txt (chmod 600)
#   PREVIEW_STATE_DIR    where the generated STAFF_USERS and SESSION_SECRET are
#                        kept between runs, default ~/.config/waterville-preview (chmod 700)
#   MIN_REPLICAS         0 (default) scales to zero when idle; 1 keeps it warm
#   REFRESH              auto (default): run the preview refresh job when it has
#                        never succeeded; 1: always; 0: never
#   SMOKE                1 (default) runs the smoke test; 0 skips it
#   STAFF_LOGIN_USER / STAFF_LOGIN_PASSWORD
#                        account for the staff smoke test when STAFF_USERS is
#                        yours (the demo account is used otherwise)
set -euo pipefail
cd "$(dirname "$0")/.."

RG=${RESOURCE_GROUP:-rg-waterville-rag}
ENV_NAME=waterville-env
APP=waterville-preview
JOB=waterville-preview-refresh
INDEX=waterville-code-preview
TEMPLATE=infra/preview.bicep
DEPLOYMENT=waterville-preview
MIN_REPLICAS=${MIN_REPLICAS:-0}
REFRESH=${REFRESH:-auto}
SMOKE=${SMOKE:-1}
CREDS=${PREVIEW_CREDENTIALS:-$HOME/waterville-preview-credentials.txt}
STATE=${PREVIEW_STATE_DIR:-$HOME/.config/waterville-preview}
DEMO_USER=inspector
WHAT_IF_ONLY=0
[ "${1:-}" = --what-if ] && WHAT_IF_ONLY=1

log() { printf '\n==> %s\n' "$*" >&2; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

# The two production resources this script must never change.
PROD_APP=waterville-app
PROD_JOB=waterville-refresh
case "$TEMPLATE" in *main.bicep) die "refusing to deploy main.bicep from the preview script" ;; esac
for n in "$APP" "$JOB"; do
  [ "$n" != "$PROD_APP" ] && [ "$n" != "$PROD_JOB" ] || die "preview name $n is a production name"
done

for v in AZURE_CLIENT_ID AZURE_CLIENT_SECRET AZURE_TENANT_ID AZURE_SUBSCRIPTION_ID; do
  [ -n "${!v:-}" ] || die "$v is not set"
done
for t in az jq curl uv; do command -v "$t" >/dev/null || die "$t is not installed"; done
[ "$WHAT_IF_ONLY" = 1 ] || [ -n "${IMAGE:-}" ] || command -v docker >/dev/null || die "docker is not installed (or set IMAGE)"

WORK=$(mktemp -d)
chmod 700 "$WORK"
trap 'rm -rf "$WORK"' EXIT

export AZURE_CORE_ONLY_SHOW_ERRORS=1 AZURE_EXTENSION_USE_DYNAMIC_INSTALL=yes_without_prompt
log "Signing in as service principal"
# The secret goes in on stdin (az reads "@-"), never on the command line where
# ps or /proc/*/cmdline would show it. printf is a shell builtin.
printf '%s' "$AZURE_CLIENT_SECRET" | az login --service-principal -u "$AZURE_CLIENT_ID" -p @- --tenant "$AZURE_TENANT_ID" -o none
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

LOCATION=$(az containerapp env show -g "$RG" -n "$ENV_NAME" --query location -o tsv) \
  || die "Container Apps environment $ENV_NAME not found in $RG; deploy production first (infra/deploy.sh)"
az provider show -n Microsoft.Storage --query registrationState -o tsv | grep -qx Registered \
  || die "provider Microsoft.Storage is not registered; run: az provider register --namespace Microsoft.Storage"

# ------------------------------------------------------------------ existing resources
# one TYPE [QUERY]: the name of the single resource of TYPE in the group.
one() {
  local names
  names=$(az resource list -g "$RG" --resource-type "$1" --query "${2:-[].name}" -o tsv)
  [ "$(printf '%s\n' "$names" | grep -c .)" = 1 ] || die "expected one $1 in $RG, found: ${names:-none}"
  printf '%s' "$names"
}
ACR_NAME=$(one Microsoft.ContainerRegistry/registries)
SEARCH_NAME=$(one Microsoft.Search/searchServices)
OPENAI_NAME=$(one Microsoft.CognitiveServices/accounts "[?kind=='OpenAI'].name")
LOGS_NAME=$(one Microsoft.OperationalInsights/workspaces)
ACR_SERVER=$(az acr show -n "$ACR_NAME" --query loginServer -o tsv)

CHAT_MODEL=$(az cognitiveservices account deployment show -g "$RG" -n "$OPENAI_NAME" --deployment-name chat \
  --query properties.model.name -o tsv) || die "the OpenAI account has no 'chat' deployment"
EMBED_MODEL=$(az cognitiveservices account deployment show -g "$RG" -n "$OPENAI_NAME" --deployment-name embedding \
  --query properties.model.name -o tsv) || die "the OpenAI account has no 'embedding' deployment"
REASONING=""
[[ $CHAT_MODEL =~ ^(gpt-5|o[0-9]) ]] && REASONING=low
EMBED_DIMS=3072
[ "$EMBED_MODEL" = text-embedding-3-large ] || EMBED_DIMS=1536
log "Reusing $ENV_NAME ($LOCATION), $ACR_NAME, $SEARCH_NAME, $OPENAI_NAME (chat: $CHAT_MODEL), $LOGS_NAME"

# Production fingerprint, compared again after the deploy.
prod_state() {
  {
    az containerapp show -g "$RG" -n "$PROD_APP" \
      --query "[properties.latestRevisionName, properties.template.containers[0].image]" -o tsv 2>/dev/null || echo "no $PROD_APP"
    az containerapp job show -g "$RG" -n "$PROD_JOB" \
      --query "[properties.template.containers[0].image, properties.configuration.triggerType]" -o tsv 2>/dev/null || echo "no $PROD_JOB"
  } | tr '\t\n' '  '
}
PROD_BEFORE=$(prod_state)

# ------------------------------------------------------------------ secrets
# Kept in STATE so redeploys keep the same staff passwords and sessions.
mkdir -p "$STATE"
chmod 700 "$STATE"
umask 077
NEW_DEMO_PASSWORD=""
if [ -z "${SESSION_SECRET:-}" ]; then
  if [ -s "$STATE/session-secret" ]; then
    SESSION_SECRET=$(cat "$STATE/session-secret")
  elif [ "$WHAT_IF_ONLY" = 1 ]; then
    SESSION_SECRET=what-if-placeholder
  else
    SESSION_SECRET=$(uv run --quiet python -m app.auth secret)
    printf '%s\n' "$SESSION_SECRET" > "$STATE/session-secret"
    log "Generated SESSION_SECRET (kept in $STATE/session-secret)"
  fi
fi
if [ -z "${STAFF_USERS:-}" ]; then
  if [ -s "$STATE/staff-users.json" ]; then
    STAFF_USERS=$(cat "$STATE/staff-users.json")
  elif [ "$WHAT_IF_ONLY" = 1 ]; then
    STAFF_USERS='{}'
  else
    NEW_DEMO_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')
    STAFF_USERS=$(printf '%s\n' "$NEW_DEMO_PASSWORD" | uv run --quiet python -m app.auth hash "$DEMO_USER")
    printf '%s\n' "$STAFF_USERS" > "$STATE/staff-users.json"
    log "Created the demo staff account '$DEMO_USER'"
  fi
fi
jq -e 'type == "object" and length > 0' >/dev/null 2>&1 <<<"$STAFF_USERS" || \
  [ "$WHAT_IF_ONLY" = 1 ] || die "STAFF_USERS must be a non-empty JSON object of username to hash"

# ------------------------------------------------------------------ image
if [ -n "${IMAGE:-}" ]; then
  log "Using image $IMAGE"
elif [ "$WHAT_IF_ONLY" = 1 ]; then
  IMAGE=$(az containerapp show -g "$RG" -n "$APP" --query "properties.template.containers[0].image" -o tsv 2>/dev/null || true)
  IMAGE=${IMAGE:-$ACR_SERVER/waterville:preview-whatif}
else
  TAG="preview-$(git rev-parse --short HEAD)"
  git diff --quiet HEAD -- ecode app web infra Dockerfile pyproject.toml uv.lock tests/fixtures \
    && [ -z "$(git status --porcelain --untracked-files=normal -- ecode app web infra tests/fixtures)" ] \
    || TAG="$TAG-dirty-$(date +%s)"
  IMAGE="$ACR_SERVER/waterville:$TAG"
  log "Building and pushing $IMAGE"
  docker build -t "$IMAGE" .
  az acr login -n "$ACR_NAME"
  docker push "$IMAGE"
fi

# ------------------------------------------------------------------ parameters
# Secure values go through a 600 file, never the command line.
PARAMS="$WORK/params.json"
STAFF_USERS="$STAFF_USERS" SESSION_SECRET="$SESSION_SECRET" jq -n \
  --arg location "$LOCATION" --arg image "$IMAGE" --arg env "$ENV_NAME" --arg acr "$ACR_NAME" \
  --arg search "$SEARCH_NAME" --arg openai "$OPENAI_NAME" --arg logs "$LOGS_NAME" \
  --arg reasoning "$REASONING" --arg embedModel "$EMBED_MODEL" --argjson embedDims "$EMBED_DIMS" \
  --arg name "$APP" --arg index "$INDEX" --argjson minReplicas "$MIN_REPLICAS" '{
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
    contentVersion: "1.0.0.0",
    parameters: {
      location: {value: $location}, image: {value: $image}, envName: {value: $env},
      acrName: {value: $acr}, searchName: {value: $search}, openAiName: {value: $openai},
      logsName: {value: $logs}, chatReasoningEffort: {value: $reasoning},
      embeddingModel: {value: $embedModel}, embeddingDimensions: {value: $embedDims},
      name: {value: $name}, searchIndex: {value: $index}, minReplicas: {value: $minReplicas},
      staffUsers: {value: env.STAFF_USERS}, sessionSecret: {value: env.SESSION_SECRET}
    }}' > "$PARAMS"

# ------------------------------------------------------------------ what-if gate
log "What-if for $TEMPLATE"
az deployment group what-if -g "$RG" -n "$DEPLOYMENT" -f "$TEMPLATE" -p @"$PARAMS" \
  --no-pretty-print -o json > "$WORK/whatif.json"
jq -r '.changes[] | "  \(.changeType)\t\(.resourceId | sub("^/subscriptions/[^/]+/resourceGroups/[^/]+/providers/"; ""))"' \
  "$WORK/whatif.json" | sort >&2
# Anything other than creating new resources or changing preview ones is a stop.
BAD=$(jq -r --arg app "$APP" '.changes[]
  | select(.changeType != "Create" and .changeType != "NoChange" and .changeType != "Ignore")
  | select((.resourceId | test("/(" + $app + "|" + $app + "-refresh|" + $app + "-id|" + $app + "-refresh-id|wvpreview[a-z0-9]*)(/|$)")) | not)
  | select((.resourceId | test("/providers/Microsoft.Authorization/roleAssignments/")) | not)
  | "\(.changeType) \(.resourceId)"' "$WORK/whatif.json")
[ -z "$BAD" ] || die "the what-if would change existing non-preview resources:
$BAD"
if jq -e '.changes[] | select(.changeType == "Delete")' "$WORK/whatif.json" >/dev/null; then
  die "the what-if would delete a resource; refusing"
fi
log "What-if: only new or preview resources change"
if [ "$WHAT_IF_ONLY" = 1 ]; then
  jq -r '[.changes[].changeType] | group_by(.) | map("\(.[0]): \(length)") | join(", ")' "$WORK/whatif.json"
  exit 0
fi

# ------------------------------------------------------------------ deploy
FIRST_DEPLOY=0
az containerapp show -g "$RG" -n "$APP" -o none 2>/dev/null || FIRST_DEPLOY=1
log "Deploying $TEMPLATE"
OUT=$(az deployment group create -g "$RG" -n "$DEPLOYMENT" -f "$TEMPLATE" -p @"$PARAMS" \
  --query properties.outputs -o json)
APP_URL=$(jq -r .appUrl.value <<<"$OUT")
[ "$(jq -r .searchIndex.value <<<"$OUT")" = "$INDEX" ] || die "deployment reports an unexpected index"

# ------------------------------------------------------------------ preview index and its role
# The refresh job may write documents in the preview index and nowhere else on
# the search service. This script, not the job, creates and updates the index
# definition, and grants the job's identity Search Index Data Contributor at
# the index scope (Bicep cannot declare a role assignment on an index).
[ "$INDEX" != waterville-code ] || die "refusing to manage the production index"
SEARCH_ID=$(jq -r .searchId.value <<<"$OUT")
JOB_PRINCIPAL=$(jq -r .jobPrincipalId.value <<<"$OUT")
INDEX_SCOPE="$SEARCH_ID/indexes/$INDEX"
log "Creating or updating the index definition of $INDEX"
SEARCH_KEY=$(az search admin-key show -g "$RG" --service-name "$SEARCH_NAME" --query primaryKey -o tsv 2>/dev/null || true)
OPENAI_ENDPOINT=$(az cognitiveservices account show -g "$RG" -n "$OPENAI_NAME" --query properties.endpoint -o tsv)
# The key (when the service allows keys) goes through the environment of this
# one command; without it the service principal's Entra token is used.
AZURE_SEARCH_API_KEY="$SEARCH_KEY" AZURE_SEARCH_ENDPOINT="https://$SEARCH_NAME.search.windows.net" \
  AZURE_SEARCH_INDEX="$INDEX" AZURE_OPENAI_ENDPOINT="$OPENAI_ENDPOINT" \
  AZURE_OPENAI_EMBEDDING_DEPLOYMENT=embedding AZURE_OPENAI_EMBEDDING_MODEL="$EMBED_MODEL" \
  EMBEDDING_DIMENSIONS="$EMBED_DIMS" uv run --quiet python -m ecode.azure ensure-index
unset SEARCH_KEY

ROLE_INDEX_WRITER="Search Index Data Contributor"
HAVE=$(az role assignment list --assignee "$JOB_PRINCIPAL" --scope "$INDEX_SCOPE" --role "$ROLE_INDEX_WRITER" \
  --query "length(@)" -o tsv 2>/dev/null || echo 0)
if [ "${HAVE:-0}" = 0 ]; then
  log "Granting the refresh job '$ROLE_INDEX_WRITER' on index $INDEX only"
  az role assignment create --assignee-object-id "$JOB_PRINCIPAL" --assignee-principal-type ServicePrincipal \
    --role "$ROLE_INDEX_WRITER" --scope "$INDEX_SCOPE" -o none
fi
# Earlier versions of preview.bicep gave the job service-wide search roles,
# which reach the production index. Remove any that are left.
az role assignment list --assignee "$JOB_PRINCIPAL" --all -o json \
  | jq -r --arg s "$SEARCH_ID" '.[] | select((.scope | ascii_downcase) == ($s | ascii_downcase))
      | select(.roleDefinitionName | test("^Search ")) | .id' \
  | while read -r ID; do
      [ -n "$ID" ] || continue
      log "Removing a service-wide search role from the refresh job ($ID)"
      az role assignment delete --ids "$ID" -o none
    done \
  || warn "could not check the refresh job for service-wide search roles; check its role assignments by hand"

if [ -n "$NEW_DEMO_PASSWORD" ]; then
  {
    printf 'Waterville preview staff sign-in\n'
    printf 'URL:      %s/staff/login\n' "$APP_URL"
    printf 'Username: %s\n' "$DEMO_USER"
    printf 'Password: %s\n' "$NEW_DEMO_PASSWORD"
    printf 'Created:  %s\n' "$(date -u +%Y-%m-%dT%H:%MZ)"
    printf '\nDemo account for the preview only. Replace it with real accounts:\n'
    printf '  STAFF_USERS=... infra/deploy-preview.sh   (see docs/preview.md)\n'
  } > "$CREDS"
  chmod 600 "$CREDS"
  log "Demo staff password written to $CREDS"
fi

# ------------------------------------------------------------------ refresh
LOADED=$(az containerapp job execution list -g "$RG" -n "$JOB" \
  --query "length([?properties.status=='Succeeded'])" -o tsv 2>/dev/null || echo 0)
RUN_REFRESH=0
case "$REFRESH" in
  1) RUN_REFRESH=1 ;;
  auto) [ "${LOADED:-0}" -gt 0 ] || RUN_REFRESH=1 ;;
esac
if [ "$RUN_REFRESH" = 1 ]; then
  if [ "$FIRST_DEPLOY" = 1 ]; then
    log "Waiting 2 minutes for new role assignments to propagate"
    sleep 120
  fi
  PREVIEW_SKIP_LOGIN=1 RESOURCE_GROUP="$RG" PREVIEW_JOB="$JOB" infra/refresh-preview.sh
  LOADED=1
elif [ "${LOADED:-0}" = 0 ]; then
  warn "the preview index has never been loaded; answers will fail until infra/refresh-preview.sh runs"
fi

# ------------------------------------------------------------------ smoke test
if [ "$SMOKE" = 1 ]; then
  log "Smoke test against $APP_URL (the first request wakes a scaled-to-zero app)"
  ok=0
  for _ in $(seq 1 40); do
    if curl -fsS --max-time 20 "$APP_URL/healthz" >/dev/null 2>&1; then ok=1; break; fi
    sleep 6
  done
  [ "$ok" = 1 ] || die "/healthz did not answer"
  curl -fsS -D "$WORK/headers" -o /dev/null "$APP_URL/" || die "/ did not answer"
  grep -qi '^x-robots-tag: *noindex' "$WORK/headers" || die "the preview does not send X-Robots-Tag: noindex"
  curl -fsS -o /dev/null "$APP_URL/staff/login" || die "/staff/login did not answer"

  ANSWER=$(curl -fsS -N --max-time 120 "$APP_URL/api/chat" -H 'Content-Type: application/json' \
    -d '{"messages":[{"role":"user","content":"Do I need a permit to build a fence?"}]}' \
    | sed -n 's/^data: //p' | jq -rj 'objects | select(.text) | .text' || true)
  if [ -n "$ANSWER" ]; then
    printf '%s\n' "$ANSWER" | head -8
  elif [ "${LOADED:-0}" = 0 ]; then
    warn "public question returned no answer (the preview index is not loaded yet)"
  else
    die "public question returned no answer"
  fi

  LOGIN_USER=${STAFF_LOGIN_USER:-}
  LOGIN_PASSWORD=${STAFF_LOGIN_PASSWORD:-}
  if [ -z "$LOGIN_USER" ] && [ -r "$CREDS" ] && jq -e --arg u "$DEMO_USER" 'has($u)' >/dev/null <<<"$STAFF_USERS"; then
    LOGIN_USER=$DEMO_USER
    LOGIN_PASSWORD=$(sed -n 's/^Password: //p' "$CREDS")
  fi
  if [ -n "$LOGIN_USER" ] && [ -n "$LOGIN_PASSWORD" ]; then
    JAR="$WORK/cookies"
    U="$LOGIN_USER" P="$LOGIN_PASSWORD" jq -n '{username: env.U, password: env.P}' \
      | curl -fsS -c "$JAR" -o /dev/null "$APP_URL/api/staff/login" \
          -H 'Content-Type: application/json' -H 'X-Requested-With: wv' --data-binary @- \
      || die "staff login failed for $LOGIN_USER"
    ME_ENV=$(curl -fsS -b "$JAR" "$APP_URL/api/staff/me" | jq -r .env)
    [ "$ME_ENV" = preview ] || die "/api/staff/me reports env '$ME_ENV', expected preview"
    STAFF=$(curl -fsS -N --max-time 180 -b "$JAR" "$APP_URL/api/chat" -H 'Content-Type: application/json' \
      -H 'X-Requested-With: wv' \
      -d '{"mode":"staff","messages":[{"role":"user","content":"What notice does § 205-7 require before a penalty?"}]}' || true)
    grep -q '"mode": "staff"' <<<"$STAFF" || die "staff chat did not answer in staff mode"
    curl -fsS -b "$JAR" -o /dev/null -X POST -H 'X-Requested-With: wv' "$APP_URL/api/staff/logout" || true
    log "Staff sign-in, /api/staff/me and a staff-mode answer work for $LOGIN_USER"
  else
    warn "no staff password at hand; skipped the staff sign-in check (set STAFF_LOGIN_USER and STAFF_LOGIN_PASSWORD)"
  fi
fi

# ------------------------------------------------------------------ production untouched
PROD_AFTER=$(prod_state)
[ "$PROD_BEFORE" = "$PROD_AFTER" ] || die "production changed during the deploy:
before: $PROD_BEFORE
after:  $PROD_AFTER"
log "Production unchanged: $PROD_AFTER"

log "Preview ready: $APP_URL"
printf 'Staff sign-in: %s/staff/login\n' "$APP_URL"
[ -r "$CREDS" ] && printf 'Demo credentials: %s\n' "$CREDS"
printf 'Run the eval: uv run python eval/run.py --url %s\n' "$APP_URL"
