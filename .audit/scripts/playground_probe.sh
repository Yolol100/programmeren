#!/usr/bin/env bash
set -euo pipefail

RESULTS="${RESULTS_DIR:-${GITHUB_WORKSPACE:-$PWD}/audit-results/playground}"
PORT="${PLAYGROUND_PORT:-9401}"
mkdir -p "$RESULTS"

npx --yes @wp-playground/cli@3.1.53 \
  server --wp=7.1 --php=8.3 --port="$PORT" > "$RESULTS/server.log" 2>&1 &
pid=$!
printf '%s\n' "$pid" > "$RESULTS/server.pid"
cleanup() { kill "$pid" 2>/dev/null || true; }
trap cleanup EXIT

ready=0
for attempt in $(seq 1 45); do
  if curl -fsS "http://127.0.0.1:${PORT}/" -o "$RESULTS/homepage.html"; then
    ready=1
    break
  fi
  sleep 2
done

if [[ "$ready" != "1" ]]; then
  cat "$RESULTS/server.log" >&2
  exit 1
fi
curl -fsS "http://127.0.0.1:${PORT}/wp-json/" -o "$RESULTS/rest-index.json"
printf 'playground_cli=3.1.53\nwordpress=7.1\nphp=8.3\nstatus=ready\n' > "$RESULTS/runtime.txt"
