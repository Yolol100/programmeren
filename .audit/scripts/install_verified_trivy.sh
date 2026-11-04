#!/usr/bin/env bash
set -euo pipefail

# GitHub release asset pinned to its official SHA-256 digest.
# Bounded retries handle transient release-asset DNS/CDN failures.
version='0.74.0'
sha256='2ae6fe3ee734b7fdf11335663e18c75ea12dccc76062f09f164a3b0f8be4371a'
archive="$(mktemp "$RUNNER_TEMP/trivy-XXXXXX.tar.gz")"
trap 'rm -f "$archive"' EXIT

curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 \
  --retry 5 --retry-delay 2 --retry-all-errors \
  'https://github.com/aquasecurity/trivy/releases/download/v0.74.0/trivy_0.74.0_Linux-64bit.tar.gz' \
  --output "$archive"
printf '%s  %s\n' "$sha256" "$archive" | sha256sum --check --strict

bin_dir="$RUNNER_TEMP/webactueel-trivy-verified"
mkdir -p "$bin_dir"
tar -xzf "$archive" -C "$bin_dir" trivy
test -x "$bin_dir/trivy"
actual="$("$bin_dir/trivy" --version | sed -n 's/^Version: //p' | head -n 1)"
if [[ "$actual" != "$version" ]]; then
  echo "Pinned Trivy CLI mismatch: expected $version, got $actual" >&2
  exit 1
fi
printf '%s\n' "$bin_dir" >> "$GITHUB_PATH"
printf 'Verified Trivy %s against official SHA-256\n' "$version"
