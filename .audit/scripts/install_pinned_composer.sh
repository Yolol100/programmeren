#!/usr/bin/env bash
set -euo pipefail

# Composer's canonical immutable release archive; setup-php's installer may
# resolve a moving stable build even when a checksum-pinned version is requested.
COMPOSER_VERSION="2.10.3"
COMPOSER_SHA256="7a2d379d5b8ffdaa028580ef26494c36d2feef4b178d3dd1473a4dbc5e17c8d6"
TMP_DIR="${RUNNER_TEMP:-/tmp}"
BIN_DIR="$TMP_DIR/webactueel-pinned-composer-bin"
PHAR_FILE="$(mktemp "$TMP_DIR/composer-2.10.3-XXXXXX.phar")"
trap 'rm -f "$PHAR_FILE"' EXIT

curl --fail --silent --show-error --location --retry 2 --proto '=https' --tlsv1.2 \
  "https://getcomposer.org/download/${COMPOSER_VERSION}/composer.phar" -o "$PHAR_FILE"
printf '%s  %s\n' "$COMPOSER_SHA256" "$PHAR_FILE" | sha256sum -c -
mkdir -p "$BIN_DIR"
install -m 0755 "$PHAR_FILE" "$BIN_DIR/composer"
printf '%s  %s\n' "$COMPOSER_SHA256" "$BIN_DIR/composer" | sha256sum -c -
printf '%s\n' "$BIN_DIR" >> "${GITHUB_PATH:-/dev/null}"
export PATH="$BIN_DIR:$PATH"
ACTUAL_VERSION="$(composer --no-ansi --version | awk '{print $3}')"
if [[ "$ACTUAL_VERSION" != "$COMPOSER_VERSION" ]]; then
  echo "Audit Composer CLI drift: expected $COMPOSER_VERSION, got $ACTUAL_VERSION" >&2
  exit 2
fi
printf 'Pinned Composer CLI %s verified against official SHA-256\n' "$ACTUAL_VERSION"
