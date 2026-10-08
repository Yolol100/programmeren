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
private="$(python3 -c 'import json,sys; v=json.load(sys.stdin).get("private"); print("true" if v is True else "false" if v is False else "unknown")' <<<"$metadata")"
visibility="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("visibility", "unknown"))' <<<"$metadata")"

echo "Target visibility: ${visibility}"
if [[ "$HARNESS_VISIBILITY" != "public" && "$HARNESS_VISIBILITY" != "private" ]]; then
  echo "Unknown or unsupported harness visibility; refusing audit." >&2
  exit 3
fi
if [[ "$HARNESS_VISIBILITY" == "public" && ( "$private" != "false" || "$visibility" != "public" ) ]]; then
  echo "Refusing to audit a non-public or unverified target from a public harness because logs/artifacts could expose non-public code or findings." >&2
  exit 3
fi
