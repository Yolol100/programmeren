#!/usr/bin/env bash
set -uo pipefail

RESULTS="${GITHUB_WORKSPACE:-$PWD}/audit-results"
mkdir -p "$RESULTS"

if ! command -v wp-env >/dev/null 2>&1; then
  echo "wp-env is not available; Plugin Check runtime did not initialize." | tee "$RESULTS/runtime.log"
  exit 2
fi

slug="${PLUGIN_SLUG:-}"
if [[ -z "$slug" ]]; then
  echo "PLUGIN_SLUG is not set by Plugin Check action." | tee "$RESULTS/runtime.log"
  exit 2
fi

exec > >(tee "$RESULTS/runtime.log") 2>&1

set +e
wp-env run cli wp config set WP_DEBUG true --raw
wp-env run cli wp config set WP_DEBUG_LOG true --raw
wp-env run cli wp config set WP_DEBUG_DISPLAY false --raw
wp-env run cli wp plugin deactivate "$slug"
deactivate_code=$?
wp-env run cli wp plugin activate "$slug"
activate_code=$?

curl -fsS -o "$RESULTS/homepage.html" -w 'homepage_http=%{http_code}\nhomepage_starttransfer=%{time_starttransfer}\nhomepage_total=%{time_total}\n' http://127.0.0.1:8880/ | tee "$RESULTS/http-timing.txt"
home_code=${PIPESTATUS[0]}
curl -fsS -o "$RESULTS/rest-index.json" -w 'rest_http=%{http_code}\nrest_starttransfer=%{time_starttransfer}\nrest_total=%{time_total}\n' http://127.0.0.1:8880/wp-json/ | tee -a "$RESULTS/http-timing.txt"
rest_code=${PIPESTATUS[0]}

wp-env run cli bash -lc 'if [ -f wp-content/debug.log ]; then cat wp-content/debug.log; fi' > "$RESULTS/wp-debug.log" 2>&1
debug_read_code=$?
set -e

runtime_fail=0
if [[ $activate_code -ne 0 || $home_code -ne 0 || $rest_code -ne 0 ]]; then
  runtime_fail=1
fi

# Treat fatal/error/uncaught/parse messages as runtime failures; notices/deprecations remain evidence.
if [[ -s "$RESULTS/wp-debug.log" ]] && grep -Eiq 'PHP (Fatal error|Parse error)|Uncaught (Error|Exception)|Allowed memory size .* exhausted' "$RESULTS/wp-debug.log"; then
  runtime_fail=1
fi

printf 'deactivate_exit=%s\nactivate_exit=%s\nhome_exit=%s\nrest_exit=%s\ndebug_read_exit=%s\n' \
  "$deactivate_code" "$activate_code" "$home_code" "$rest_code" "$debug_read_code" > "$RESULTS/runtime-status.txt"

exit "$runtime_fail"
