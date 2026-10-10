#!/usr/bin/env bash
# Push the image the pipeline tested to Alice's registry (the same image, never a rebuild). Run by the deploy job in
# .github/workflows/deploy.yml after azure/login; tested without Azure by tests/test_push_image.py (stand-in az and docker).
#
#   ACR=<registry name> SHA=<full commit> bash deploy/push_image.sh [image.tar.gz]
#
# Writes IMAGE and TAG to $GITHUB_ENV for the steps after it.
#
# Why the retries (10 Oct 2026): the #45 release stopped here with "ERROR: JSON is invalid: Expecting value: line 1 column 1
# (char 0)" from `az acr login`, 12 seconds after the image loaded. The workflow parses no JSON in this step; the empty answer
# came from Azure during the registry sign-in (the identical step had passed 30 minutes earlier on main, same identity and
# subject). Each Azure call that can fail like that is now tried up to AZ_TRIES times with a pause, and a final failure says
# which call failed and shows the CLI's own diagnostics (--debug, with anything that looks like a token removed).
set -euo pipefail
ARCHIVE="${1:-image.tar.gz}"
: "${ACR:?ACR (the registry name) is not set}"
: "${SHA:?SHA (the commit being released) is not set}"
TRIES="${AZ_TRIES:-4}"
PAUSE="${AZ_PAUSE:-10}"
TAG="$(printf '%s' "$SHA" | cut -c1-7)"
IMAGE="$ACR.azurecr.io/alice:$TAG"
ERR="$(mktemp)"
trap 'rm -f "$ERR"' EXIT

# Run "$@" until it succeeds, at most $TRIES times. Its error output is shown on every failed try, so a log says what happened.
retry() {
  local what="$1"; shift
  local i
  for i in $(seq 1 "$TRIES"); do
    if "$@" 2>"$ERR"; then cat "$ERR" >&2; return 0; fi
    echo "::warning::$what failed (try $i of $TRIES): $(head -c 600 "$ERR" | tr '\n' ' ')"
    [ "$i" -lt "$TRIES" ] && sleep $((PAUSE * i))
  done
  return 1
}

# The CLI's own account of a failed call, without secrets: lines naming a token, an assertion, a password or an
# Authorization header are left out, and so is anything that looks like a JWT.
diagnose() {
  "$@" --debug 2>&1 | grep -viE 'token|assertion|password|authorization|secret' \
    | sed -E 's/eyJ[A-Za-z0-9._-]{20,}/(removed)/g' | tail -60 || true
}

echo "Loading the tested image"
gunzip -c "$ARCHIVE" | docker load

echo "Signing in to the registry $ACR"
if ! retry "az acr login" az acr login -n "$ACR" --only-show-errors; then
  echo "::error::Could not sign in to the registry $ACR after $TRIES tries. Nothing was pushed and nothing changed in Azure."
  echo "What the Azure CLI did on one more try (tokens removed):"
  diagnose az acr login -n "$ACR"
  exit 1
fi

echo "Pushing $IMAGE"
docker tag "alice:$SHA" "$IMAGE"
if ! retry "docker push" docker push "$IMAGE"; then
  echo "::error::Could not push $IMAGE after $TRIES tries. Nothing changed in Azure."
  exit 1
fi

if [ -n "${GITHUB_ENV:-}" ]; then
  echo "IMAGE=$IMAGE" >> "$GITHUB_ENV"
  echo "TAG=$TAG" >> "$GITHUB_ENV"
fi
echo "Pushed $IMAGE"
