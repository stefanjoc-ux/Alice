#!/bin/sh
# Starts Alice's processes for this container's role. If any process stops, the container stops too, so Azure restarts it.
set -e
mkdir -p "$AISUBSTRATE_DATA_DIR" 2>/dev/null || true
case "${ALICE_ROLE:-web}" in
  web)
    # Internal MCP server for the web chat: bound to 127.0.0.1 inside the container only (rule 9: never exposed).
    python mcp_server.py &
    MCP=$!
    python -m uvicorn app:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' &
    WEB=$!
    # Stop the container as soon as either process ends.
    while kill -0 $MCP 2>/dev/null && kill -0 $WEB 2>/dev/null; do sleep 5; done
    echo "A process stopped; exiting so the container is restarted." >&2
    kill $MCP $WEB 2>/dev/null || true
    exit 1
    ;;
  mcp)
    export ALICE_EXT_HOST="${ALICE_EXT_HOST:-0.0.0.0}"
    exec python mcp_server.py --external
    ;;
  migrate)
    # One-off cut-over job: copy the SQLite database (uploaded to the file share) into PostgreSQL. Dry run unless MIGRATE_APPLY=1.
    # Run it before the apps first start (empty database). MIGRATE_REPLACE=1 empties the target's Alice tables first.
    export ALICE_MIGRATE_TARGET_URL="${ALICE_MIGRATE_TARGET_URL:-$ALICE_DATABASE_URL}"
    set -- --source "${MIGRATE_SOURCE:-/mnt/alice/data/substrate.db}"
    [ "${MIGRATE_REPLACE:-0}" = "1" ] && set -- "$@" --replace
    [ "${MIGRATE_APPLY:-0}" = "1" ] && set -- "$@" --apply
    exec python migrate_to_postgres.py "$@"
    ;;
  test)
    exec python tests/run_tests.py "$@"
    ;;
  backup)
    # Nightly off-site copy (backup.py): pg_dump of the live database and the file share (mounted READ-ONLY at /mnt/alice-ro),
    # compressed, to the separate off-site storage account. Scheduled at 01:00 and 02:00 UTC; only the one at 02:00 UK time runs.
    exec python backup.py run
    ;;
  *)
    echo "Unknown ALICE_ROLE: $ALICE_ROLE (use web, mcp, migrate, test or backup)" >&2; exit 2 ;;
esac
