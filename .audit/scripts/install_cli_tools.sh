#!/usr/bin/env bash
set -euo pipefail

BIN_DIR="${RUNNER_TEMP:-/tmp}/programmeren-audit-bin"
RESULTS_DIR="${GITHUB_WORKSPACE:-$PWD}/audit-results"
mkdir -p "$BIN_DIR" "$RESULTS_DIR"

# actionlint v1.7.12 (release asset digest verified against GitHub release metadata).
actionlint_archive="${RUNNER_TEMP:-/tmp}/actionlint_1.7.12_linux_amd64.tar.gz"
curl -fsSL -o "$actionlint_archive" "https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_linux_amd64.tar.gz"
echo "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8  $actionlint_archive" | sha256sum -c -
tar -xzf "$actionlint_archive" -C "$BIN_DIR" actionlint

# Gitleaks v8.30.1 (release asset digest verified against GitHub release metadata).
gitleaks_archive="${RUNNER_TEMP:-/tmp}/gitleaks_8.30.1_linux_x64.tar.gz"
curl -fsSL -o "$gitleaks_archive" "https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz"
echo "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb  $gitleaks_archive" | sha256sum -c -
tar -xzf "$gitleaks_archive" -C "$BIN_DIR" gitleaks

# Isolate zizmor from the runner Python and require the exact Linux x86-64 PyPI wheel digest.
zizmor_venv="${RUNNER_TEMP:-/tmp}/zizmor-venv"
zizmor_requirements="${RUNNER_TEMP:-/tmp}/zizmor-requirements.txt"
python3 -m venv "$zizmor_venv"
printf '%s\n' 'zizmor==1.29.0 --hash=sha256:587b99c2e1b34575c6c8565c2bfde415ca8bc0310f5589f19bc948c8dea10a20' > "$zizmor_requirements"
"$zizmor_venv/bin/python" -m pip install \
  --disable-pip-version-check \
  --no-input \
  --only-binary=:all: \
  --require-hashes \
  --no-deps \
  -r "$zizmor_requirements"
ln -sf "$zizmor_venv/bin/zizmor" "$BIN_DIR/zizmor"

# Semgrep Community Edition is local-only here. Do not login, start MCP, use remote registry configs,
# or upload findings. The exact CLI version is pinned; scans use only the repository-owned rule file
# with metrics explicitly disabled. Record the resolved dependency graph rather than claiming it is hash-locked.
semgrep_venv="${RUNNER_TEMP:-/tmp}/semgrep-venv"
python3 -m venv "$semgrep_venv"
"$semgrep_venv/bin/python" -m pip install \
  --disable-pip-version-check \
  --no-input \
  "semgrep==1.177.0"
ln -sf "$semgrep_venv/bin/semgrep" "$BIN_DIR/semgrep"
"$semgrep_venv/bin/semgrep" --version > "$RESULTS_DIR/semgrep-version.txt"
"$semgrep_venv/bin/python" -m pip freeze | LC_ALL=C sort > "$RESULTS_DIR/semgrep-python-deps.txt"

echo "$BIN_DIR" >> "$GITHUB_PATH"
