#!/usr/bin/env bash
set -euo pipefail

BIN_DIR="${RUNNER_TEMP:-/tmp}/programmeren-audit-bin"
mkdir -p "$BIN_DIR"

# actionlint v1.7.12 (release asset digest verified against GitHub release metadata).
actionlint_archive="${RUNNER_TEMP:-/tmp}/actionlint_1.7.12_linux_amd64.tar.gz"
curl -fsSL -o "$actionlint_archive" "https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_linux_amd64.tar.gz"
echo "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8  $actionlint_archive" | sha256sum -c -
tar -xzf "$actionlint_archive" -C "$BIN_DIR" actionlint

# Gitleaks v8.28.0 is pinned to a known release asset and verified by SHA-256.
gitleaks_archive="${RUNNER_TEMP:-/tmp}/gitleaks_8.28.0_linux_x64.tar.gz"
curl -fsSL -o "$gitleaks_archive" "https://github.com/gitleaks/gitleaks/releases/download/v8.28.0/gitleaks_8.28.0_linux_x64.tar.gz"
echo "a65b5253807a68ac0cafa4414031fd740aeb55f54fb7e55f386acb52e6a840eb  $gitleaks_archive" | sha256sum -c -
tar -xzf "$gitleaks_archive" -C "$BIN_DIR" gitleaks

# Isolate Python package installation from the runner system Python.
python3 -m venv "${RUNNER_TEMP:-/tmp}/zizmor-venv"
"${RUNNER_TEMP:-/tmp}/zizmor-venv/bin/python" -m pip install --disable-pip-version-check --no-input "zizmor==1.28.0"
ln -sf "${RUNNER_TEMP:-/tmp}/zizmor-venv/bin/zizmor" "$BIN_DIR/zizmor"

echo "$BIN_DIR" >> "$GITHUB_PATH"
