#!/usr/bin/env bash
set -uo pipefail

: "${PLUGIN_DIR:?PLUGIN_DIR is required}"
: "${TARGET_REPO:?TARGET_REPO is required}"
: "${TARGET_REF:?TARGET_REF is required}"

ROOT="$(realpath "$PLUGIN_DIR")"
RESULTS="${GITHUB_WORKSPACE:-$PWD}/audit-results"
TOOLS="${GITHUB_WORKSPACE:-$PWD}/.audit/tools/vendor/bin"
mkdir -p "$RESULTS"

if [[ ! -d "$ROOT" ]]; then
  echo "Plugin directory not found: $ROOT" >&2
  exit 2
fi

main_plugin=""
while IFS= read -r file; do
  if head -c 8192 "$file" | grep -Eiq '^[[:space:]]*\*?[[:space:]]*Plugin Name[[:space:]]*:'; then
    main_plugin="$file"
    break
  fi
done < <(find "$ROOT" -maxdepth 2 -type f -name '*.php' -not -path '*/vendor/*' -not -path '*/node_modules/*' | sort)

if [[ -z "$main_plugin" ]]; then
  echo "No WordPress plugin header (Plugin Name:) found under $ROOT" >&2
  exit 2
fi

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

# PHP syntax without executing plugin code.
mapfile -d '' php_files < <(find "$ROOT" -type f -name '*.php' -not -path '*/vendor/*' -not -path '*/node_modules/*' -print0)
if (( ${#php_files[@]} > 0 )); then
  run_check php-syntax "$TOOLS/parallel-lint" --no-colors --exclude "$ROOT/vendor" --exclude "$ROOT/node_modules" "$ROOT"
else
  printf 'php-syntax\tSKIP\t0\n' >> "$status_file"
fi

# WordPress Coding Standards.
run_check wpcs "$TOOLS/phpcs" -q --report=full --standard=WordPress --extensions=php --ignore='*/vendor/*,*/node_modules/*,*/build/*,*/dist/*' "$ROOT"

# PHP cross-version compatibility, anchored to the plugin header minimum.
run_check php-compat "$TOOLS/phpcs" -q --report=full --standard=PHPCompatibilityWP --runtime-set testVersion "${min_php}-" --extensions=php --ignore='*/vendor/*,*/node_modules/*,*/build/*,*/dist/*' "$ROOT"

# PHPStan with WordPress stubs/extension. Level 5 balances useful signal and false positives for heterogeneous plugins.
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

# Dependency manifests are audited without running project-defined scripts or Composer plugins.
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

if [[ -f "$ROOT/package-lock.json" ]]; then
  run_check npm-audit bash -c 'cd "$1" && npm audit --package-lock-only --audit-level=high' _ "$ROOT"
else
  printf 'npm-audit\tSKIP(no-lock)\t0\n' >> "$status_file"
fi

# Secret scan is filesystem-only: it never needs Git history or credentials.
run_check gitleaks gitleaks dir "$ROOT" --no-banner --redact --report-format json --report-path "$RESULTS/gitleaks.json"

# Local Semgrep Community Edition candidate layer. It uses only repository-owned rules,
# never logs in, never starts MCP, and disables metrics. Findings remain candidate evidence;
# Semgrep's normal scan exit code fails this check only when execution itself fails.
run_check semgrep env SEMGREP_SEND_METRICS=off semgrep scan \
  --config "${GITHUB_WORKSPACE}/.audit/semgrep/wordpress-security.yml" \
  --metrics=off \
  --json \
  --output "$RESULTS/semgrep.json" \
  "$ROOT"

# CI configuration checks apply only when the target repository contains workflows.
if [[ -d "${GITHUB_WORKSPACE}/target-repo/.github/workflows" ]]; then
  mapfile -t workflow_files < <(find "${GITHUB_WORKSPACE}/target-repo/.github/workflows" -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) | sort)
  if (( ${#workflow_files[@]} > 0 )); then
    run_check actionlint actionlint -format '{{json .}}' "${workflow_files[@]}"
    run_check zizmor zizmor --format plain --no-progress "${GITHUB_WORKSPACE}/target-repo"
  fi
else
  printf 'actionlint\tSKIP\t0\nzizmor\tSKIP\t0\n' >> "$status_file"
fi

# Source snapshot artifact; this is evidence, not a release ZIP claim.
archive="$RESULTS/${plugin_slug}-source-snapshot.zip"
(
  cd "$(dirname "$ROOT")"
  zip -qr "$archive" "$(basename "$ROOT")" \
    -x '*/.git/*' '*/node_modules/*' '*/.cache/*' '*/.phpunit.cache/*'
)
sha256sum "$archive" > "$RESULTS/source-snapshot.sha256"

if (( failures > 0 )); then
  echo "Static audit completed with ${failures} failing check(s)."
  exit 1
fi

echo "Static audit passed."
