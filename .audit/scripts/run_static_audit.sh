#!/usr/bin/env bash
set -uo pipefail

: "${PLUGIN_DIR:?PLUGIN_DIR is required}"
: "${TARGET_REPO:?TARGET_REPO is required}"
: "${TARGET_REF:?TARGET_REF is required}"

ROOT="$(realpath "$PLUGIN_DIR")"
RESULTS="${GITHUB_WORKSPACE:-$PWD}/audit-results"
TOOLS="${GITHUB_WORKSPACE:-$PWD}/.audit/tools/vendor/bin"
mkdir -p "$RESULTS"

[[ -d "$ROOT" ]] || { echo "Plugin directory not found: $ROOT" >&2; exit 2; }

main_plugin=""
while IFS= read -r file; do
  if head -c 8192 "$file" | grep -Eiq '^[[:space:]]*\*?[[:space:]]*Plugin Name[[:space:]]*:'; then
    main_plugin="$file"
    break
  fi
done < <(find "$ROOT" -maxdepth 2 -type f -name '*.php' -not -path '*/vendor/*' -not -path '*/node_modules/*' | sort)
[[ -n "$main_plugin" ]] || { echo "No WordPress plugin header (Plugin Name:) found under $ROOT" >&2; exit 2; }

min_php="$(head -c 8192 "$main_plugin" | sed -nE 's/^[[:space:]]*\*?[[:space:]]*Requires PHP[[:space:]]*:[[:space:]]*([^[:space:]]+).*/\1/ip' | head -n1)"
[[ -n "$min_php" ]] || min_php="7.4"
plugin_slug="$(basename "$ROOT")"

cat > "$RESULTS/inventory.txt" <<META
repository=$TARGET_REPO
ref=$TARGET_REF
plugin_dir=$ROOT
plugin_slug=$plugin_slug
main_plugin_file=$main_plugin
requires_php=$min_php
php_runtime=$(php -r 'echo PHP_VERSION;')
META

status_file="$RESULTS/status.tsv"
printf 'check\tstatus\texit_code\n' > "$status_file"
failures=0

run_check() {
  local name="$1"; shift
  local logfile="$RESULTS/${name}.log"
  echo "::group::${name}"
  set +e
  "$@" > >(tee "$logfile") 2>&1
  local code=$?
  if [[ $code -eq 0 ]]; then
    printf '%s\tPASS\t0\n' "$name" >> "$status_file"
  else
    printf '%s\tFAIL\t%s\n' "$name" "$code" >> "$status_file"
    failures=$((failures + 1))
  fi
  echo "::endgroup::"
}

has_profile_capability() {
  local capability="$1"
  local resolution="$RESULTS/profile-resolution.json"
  [[ -f "$resolution" ]] || return 1
  python3 - "$resolution" "$capability" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
capability = sys.argv[2]
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(2)
capabilities = data.get("capabilities")
if not isinstance(capabilities, list):
    raise SystemExit(2)
raise SystemExit(0 if capability in capabilities else 1)
PY
}

mapfile -d '' php_files < <(find "$ROOT" -type f -name '*.php' -not -path '*/vendor/*' -not -path '*/node_modules/*' -print0)
if (( ${#php_files[@]} > 0 )); then
  run_check php-syntax "$TOOLS/parallel-lint" --no-colors --exclude "$ROOT/vendor" --exclude "$ROOT/node_modules" "$ROOT"
else
  printf 'php-syntax\tSKIP\t0\n' >> "$status_file"
fi

run_check wpcs "$TOOLS/phpcs" -q --report=full --standard=WordPress --extensions=php --ignore='*/vendor/*,*/node_modules/*,*/build/*,*/dist/*' "$ROOT"
run_check php-compat "$TOOLS/phpcs" -q --report=full --standard=PHPCompatibilityWP --runtime-set testVersion "${min_php}-" --extensions=php --ignore='*/vendor/*,*/node_modules/*,*/build/*,*/dist/*' "$ROOT"

phpstan_config="$RESULTS/phpstan.neon"
cat > "$phpstan_config" <<NEON
includes:
    - ${GITHUB_WORKSPACE}/.audit/tools/vendor/szepeviktor/phpstan-wordpress/extension.neon
parameters:
    level: 5
    paths:
        - ${ROOT}
    excludePaths:
        analyse:
            - ${ROOT}/vendor/*
            - ${ROOT}/node_modules/*
            - ${ROOT}/build/*
            - ${ROOT}/dist/*
    reportUnmatchedIgnoredErrors: false
NEON
run_check phpstan "$TOOLS/phpstan" analyse --no-progress --error-format=table -c "$phpstan_config"

if [[ -f "$ROOT/composer.json" ]]; then
  run_check composer-validate composer validate --no-check-publish --working-dir="$ROOT"
  if [[ -f "$ROOT/composer.lock" ]]; then
    run_check composer-audit composer audit --locked --no-interaction --working-dir="$ROOT"
  else
    printf 'composer-audit\tSKIP(no-lock)\t0\n' >> "$status_file"
  fi
else
  printf 'composer-validate\tSKIP\t0\ncomposer-audit\tSKIP\t0\n' >> "$status_file"
fi

# PHPUnit is an explicit profile capability and must use the target project's own
# version. The audit harness never installs arbitrary target dependencies or runs
# Composer scripts merely to create a test runtime.
if has_profile_capability audit.phpunit-project; then
  if [[ ! -f "$ROOT/composer.json" ]]; then
    printf 'phpunit\tSKIP(no-composer)\t0\n' >> "$status_file"
  elif ! grep -Eq '"phpunit/phpunit"[[:space:]]*:' "$ROOT/composer.json"; then
    printf 'phpunit\tSKIP(not-declared)\t0\n' >> "$status_file"
  elif [[ ! -x "$ROOT/vendor/bin/phpunit" ]]; then
    printf 'phpunit\tSKIP(project-dependency-not-installed)\t0\n' >> "$status_file"
  else
    run_check phpunit "$ROOT/vendor/bin/phpunit" --colors=never
  fi
else
  printf 'phpunit\tSKIP(profile-disabled)\t0\n' >> "$status_file"
fi

if [[ -f "$ROOT/package-lock.json" ]]; then
  run_check npm-audit bash -c 'cd "$1" && npm audit --package-lock-only --audit-level=high' _ "$ROOT"
else
  printf 'npm-audit\tSKIP(no-lock)\t0\n' >> "$status_file"
fi

run_check gitleaks gitleaks dir "$ROOT" --no-banner --redact --report-format json --report-path "$RESULTS/gitleaks.json"
run_check semgrep env SEMGREP_SEND_METRICS=off semgrep scan --config "${GITHUB_WORKSPACE}/.audit/semgrep/wordpress-security.yml" --metrics=off --json --output "$RESULTS/semgrep.json" "$ROOT"

if [[ -d "$ROOT/.github/workflows" ]]; then
  mapfile -t workflow_files < <(find "$ROOT/.github/workflows" -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) | sort)
  if (( ${#workflow_files[@]} > 0 )); then
    run_check actionlint actionlint -format '{{json .}}' "${workflow_files[@]}"
    run_check zizmor zizmor --format plain --no-progress "$ROOT"
  else
    printf 'actionlint\tSKIP(no-workflows)\t0\nzizmor\tSKIP(no-workflows)\t0\n' >> "$status_file"
  fi
else
  printf 'actionlint\tSKIP\t0\nzizmor\tSKIP\t0\n' >> "$status_file"
fi

archive="$RESULTS/${plugin_slug}-source-snapshot.zip"
(
  cd "$(dirname "$ROOT")" &&
  zip -qr "$archive" "$(basename "$ROOT")" -x '*/.git/*' '*/node_modules/*' '*/.cache/*' '*/.phpunit.cache/*'
)
sha256sum "$archive" > "$RESULTS/source-snapshot.sha256"

if (( failures > 0 )); then
  echo "Static audit completed with ${failures} failing check(s)."
  exit 1
fi

echo "Static audit passed."
