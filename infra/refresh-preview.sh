#!/usr/bin/env bash
# Run the preview refresh job once and wait for it: crawl eCode360 and the
# state and City sources, then load the preview index (waterville-code-preview)
# and record change alerts in the preview store. Takes 20 to 40 minutes.
#
# Never touches the production job (waterville-refresh) or its index.
#
# Signs in as a service principal when AZURE_CLIENT_ID, AZURE_CLIENT_SECRET,
# AZURE_TENANT_ID and AZURE_SUBSCRIPTION_ID are set; otherwise uses the
# current `az login`.
#
# Optional:
#   RESOURCE_GROUP  default rg-waterville-rag
#   PREVIEW_JOB     default waterville-preview-refresh
#   --no-wait       start the job and print how to follow it
set -euo pipefail

RG=${RESOURCE_GROUP:-rg-waterville-rag}
JOB=${PREVIEW_JOB:-waterville-preview-refresh}
WAIT=1
[ "${1:-}" = --no-wait ] && WAIT=0

log() { printf '\n==> %s\n' "$*" >&2; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

case "$JOB" in
  waterville-refresh|waterville-app) die "$JOB is a production resource; this script runs only the preview job" ;;
  *preview*) ;;
  *) die "PREVIEW_JOB must name a preview job (got $JOB)" ;;
esac

export AZURE_CORE_ONLY_SHOW_ERRORS=1 AZURE_EXTENSION_USE_DYNAMIC_INSTALL=yes_without_prompt
if [ -z "${PREVIEW_SKIP_LOGIN:-}" ] && [ -n "${AZURE_CLIENT_ID:-}" ] && [ -n "${AZURE_CLIENT_SECRET:-}" ] && [ -n "${AZURE_TENANT_ID:-}" ]; then
  log "Signing in as service principal"
  # Secret on stdin ("@-"), never on the command line.
  printf '%s' "$AZURE_CLIENT_SECRET" | az login --service-principal -u "$AZURE_CLIENT_ID" -p @- --tenant "$AZURE_TENANT_ID" -o none
  [ -n "${AZURE_SUBSCRIPTION_ID:-}" ] && az account set --subscription "$AZURE_SUBSCRIPTION_ID"
fi

INDEX=$(az containerapp job show -g "$RG" -n "$JOB" \
  --query "properties.template.containers[0].env[?name=='AZURE_SEARCH_INDEX'].value | [0]" -o tsv) \
  || die "job $JOB not found in $RG; run infra/deploy-preview.sh first"
[ "$INDEX" != waterville-code ] || die "$JOB is set to write the production index; refusing to start it"

log "Starting $JOB (writes index $INDEX)"
EXEC=$(az containerapp job start -g "$RG" -n "$JOB" --query name -o tsv)
LOGS="az containerapp job logs show -g $RG -n $JOB --execution $EXEC --container refresh --follow"
if [ "$WAIT" = 0 ]; then
  printf 'Started %s. Follow it with:\n  %s\n' "$EXEC" "$LOGS"
  exit 0
fi

log "Waiting for $EXEC (20 to 40 minutes). Logs: $LOGS"
START=$(date +%s)
while :; do
  STATUS=$(az containerapp job execution show -g "$RG" -n "$JOB" --job-execution-name "$EXEC" \
    --query properties.status -o tsv 2>/dev/null || echo Unknown)
  case "$STATUS" in
    Succeeded) log "Preview index $INDEX loaded in $(( ($(date +%s) - START) / 60 )) minutes"; break ;;
    Failed|Stopped|Degraded) die "refresh job $EXEC ended as $STATUS; logs: $LOGS" ;;
  esac
  sleep 30
done
