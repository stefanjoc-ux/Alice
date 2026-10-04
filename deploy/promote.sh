#!/usr/bin/env bash
# Move Alice's live traffic: run by the "Promote" GitHub workflow (the button), or by hand in Cloud Shell.
#   promote.sh promote    newest revision of alice-web and alice-mcp gets 100% (only if it is Healthy, and the web app
#                         answers /healthz); the one that was live stays switched on for rollback; older ones are switched off
#   promote.sh rollback   the revision before the live one gets 100% again (switched back on first if needed)
#   promote.sh status     just show what is live
# Needs: az signed in to the subscription, RG set (default alice-rg).
set -euo pipefail
WHAT="${1:-status}"
RG="${RG:-alice-rg}"
SUMMARY="${GITHUB_STEP_SUMMARY:-/dev/null}"
az extension add --name containerapp --upgrade --only-show-errors >/dev/null 2>&1 || true

say() { echo "$*"; echo "$*" >> "$SUMMARY"; }

revisions() {  # all revisions, oldest first: name<TAB>active<TAB>traffic<TAB>health<TAB>fqdn
  az containerapp revision list -n "$1" -g "$RG" --all \
    --query "sort_by([], &properties.createdTime)[].[name, to_string(properties.active), to_string(properties.trafficWeight), properties.healthState, properties.fqdn]" -o tsv
}

show() {
  say ""; say "**$1**"; say '```'
  revisions "$1" | awk -F'\t' '$2=="true" {printf "  %-34s traffic %3s%%  %s\n", $1, $3, $4}' | tee -a "$SUMMARY"
  say '```'
}

wait_healthy() {  # app revision
  for _ in $(seq 1 30); do
    h=$(az containerapp revision show -n "$1" -g "$RG" --revision "$2" --query properties.healthState -o tsv)
    [ "$h" = "Healthy" ] && return 0
    sleep 10
  done
  return 1
}

FAILED=0
if [ "$WHAT" = "promote" ]; then   # both apps run the same image: check both first, switch both or neither
  for APP in alice-web alice-mcp; do
    ROWS=$(revisions "$APP"); LIVE=$(echo "$ROWS" | awk -F'\t' '$3+0 > 0 {print $1}' | tail -1)
    TARGET=$(echo "$ROWS" | awk -F'\t' '$2=="true" {print $1}' | tail -1)
    [ "$TARGET" = "$LIVE" ] && continue
    HEALTH=$(echo "$ROWS" | awk -F'\t' -v t="$TARGET" '$1==t {print $4}')
    if [ "$HEALTH" != "Healthy" ]; then say "$APP: $TARGET is $HEALTH, not Healthy."; FAILED=1; continue; fi
    if [ "$APP" = "alice-web" ]; then
      FQDN=$(echo "$ROWS" | awk -F'\t' -v t="$TARGET" '$1==t {print $5}')
      curl -fsS --max-time 20 "https://$FQDN/healthz" >/dev/null || { say "$APP: $TARGET did not answer its health check."; FAILED=1; }
    fi
  done
  if [ "$FAILED" = 1 ]; then
    say "Nothing was changed: the live version stays as it is."
    for APP in alice-web alice-mcp; do show "$APP"; done
    exit 1
  fi
fi
for APP in alice-web alice-mcp; do
  ROWS=$(revisions "$APP")
  LIVE=$(echo "$ROWS" | awk -F'\t' '$3+0 > 0 {print $1}' | tail -1)
  case "$WHAT" in
    status) show "$APP"; continue ;;
    promote)
      TARGET=$(echo "$ROWS" | awk -F'\t' '$2=="true" {print $1}' | tail -1)
      if [ "$TARGET" = "$LIVE" ]; then say "$APP: $LIVE is already the newest and live, nothing to do."; show "$APP"; continue; fi
      ;;
    rollback)
      [ -z "$LIVE" ] && { say "$APP: nothing is live, nothing to roll back."; continue; }
      TARGET=$(echo "$ROWS" | awk -F'\t' -v l="$LIVE" '$1==l {exit} {p=$1} END {print p}')
      if [ -z "$TARGET" ]; then say "$APP: no earlier revision to roll back to."; FAILED=1; continue; fi
      ACTIVE=$(echo "$ROWS" | awk -F'\t' -v t="$TARGET" '$1==t {print $2}')
      if [ "$ACTIVE" != "true" ]; then
        az containerapp revision activate -n "$APP" -g "$RG" --revision "$TARGET" --only-show-errors -o none
        if ! wait_healthy "$APP" "$TARGET"; then say "$APP: $TARGET was switched back on but did not become Healthy. Live stays $LIVE."; FAILED=1; continue; fi
      fi
      ;;
    *) echo "Use: promote | rollback | status"; exit 2 ;;
  esac
  az containerapp ingress traffic set -n "$APP" -g "$RG" --revision-weight "$TARGET=100" --only-show-errors -o none
  say "$APP: live is now **$TARGET** (was $LIVE)."
  if [ "$WHAT" = "promote" ]; then   # keep the new one and the one before it (for rollback); switch the rest off
    echo "$ROWS" | awk -F'\t' -v t="$TARGET" -v l="$LIVE" '$2=="true" && $1!=t && $1!=l {print $1}' | while read -r OLD; do
      az containerapp revision deactivate -n "$APP" -g "$RG" --revision "$OLD" --only-show-errors -o none && say "$APP: switched off old revision $OLD."
    done
  fi
  show "$APP"
done
exit $FAILED
