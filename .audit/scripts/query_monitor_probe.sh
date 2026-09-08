#!/usr/bin/env bash
set -euo pipefail

if [[ "${ALLOW_QUERY_MONITOR_DIAGNOSTICS:-0}" != "1" ]]; then
  echo "Query Monitor diagnostics are opt-in and may run only in a disposable wp-env runtime." >&2
  exit 2
fi
if ! command -v wp-env >/dev/null 2>&1; then
  echo "wp-env is required for Query Monitor diagnostics." >&2
  exit 2
fi

RESULTS="${RESULTS_DIR:-${GITHUB_WORKSPACE:-$PWD}/audit-results/query-monitor}"
mkdir -p "$RESULTS"
exec > >(tee "$RESULTS/query-monitor.log") 2>&1

cleanup() {
  wp-env run cli wp plugin deactivate query-monitor >/dev/null 2>&1 || true
  wp-env run cli wp plugin delete query-monitor >/dev/null 2>&1 || true
}
trap cleanup EXIT

wp-env run cli wp plugin install query-monitor --version=4.0.7 --activate
wp-env run cli wp plugin status query-monitor
wp-env run cli wp eval 'echo defined("QM_VERSION") ? QM_VERSION : "query-monitor-loaded";'
curl -fsS http://127.0.0.1:8880/ -o "$RESULTS/homepage.html"
wp-env run cli wp plugin list --name=query-monitor --format=json > "$RESULTS/plugin-status.json"
printf 'query_monitor=4.0.7\nruntime=wp-env-disposable\nstatus=active-and-probed\n' > "$RESULTS/runtime.txt"
