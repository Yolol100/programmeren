#!/usr/bin/env bash
set -euo pipefail

: "${TARGET_REPO:?TARGET_REPO is required}"
: "${HARNESS_VISIBILITY:?HARNESS_VISIBILITY is required}"

api_url="https://api.github.com/repos/${TARGET_REPO}"
args=(-fsSL -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28")
if [[ -n "${PLUGIN_REPO_TOKEN:-}" ]]; then
  args+=(-H "Authorization: Bearer ${PLUGIN_REPO_TOKEN}")
elif [[ -n "${GH_TOKEN:-}" ]]; then
  args+=(-H "Authorization: Bearer ${GH_TOKEN}")
fi

metadata="$(curl "${args[@]}" "$api_url")"
private="$(python3 -c 'import json,sys; print(str(json.load(sys.stdin).get("private", True)).lower())' <<<"$metadata")"
visibility="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("visibility", "unknown"))' <<<"$metadata")"

echo "Target visibility: ${visibility}"
if [[ "$HARNESS_VISIBILITY" == "public" && "$private" == "true" ]]; then
  echo "Refusing to audit a private target from a public harness because logs/artifacts could expose private code or findings." >&2
  exit 3
fi
