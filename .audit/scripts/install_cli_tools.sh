#!/usr/bin/env bash
set -euo pipefail

BIN_DIR="${RUNNER_TEMP:-/tmp}/programmeren-audit-bin"
mkdir -p "$BIN_DIR"

# actionlint v1.7.12 (release asset digest verified against GitHub release metadata).
actionlint_archive="${RUNNER_TEMP:-/tmp}/actionlint_1.7.12_linux_amd64.tar.gz"
curl -fsSL -o "$actionlint_archive" "https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_linux_amd64.tar.gz"
echo "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8  $actionlint_archive" | sha256sum -c -
tar -xzf "$actionlint_archive" -C "$BIN_DIR" actionlint

# Gitleaks v8.28.0 is deliberately retained and verified by SHA-256.
gitleaks_archive="${RUNNER_TEMP:-/tmp}/gitleaks_8.28.0_linux_x64.tar.gz"
curl -fsSL -o "$gitleaks_archive" "https://github.com/gitleaks/gitleaks/releases/download/v8.28.0/gitleaks_8.28.0_linux_x64.tar.gz"
echo "a65b5253807a68ac0cafa4414031fd740aeb55f54fb7e55f386acb52e6a840eb  $gitleaks_archive" | sha256sum -c -
tar -xzf "$gitleaks_archive" -C "$BIN_DIR" gitleaks

# Isolate zizmor from the runner Python and require the exact PyPI wheel digest.
zizmor_venv="${RUNNER_TEMP:-/tmp}/zizmor-venv"
zizmor_requirements="${RUNNER_TEMP:-/tmp}/zizmor-requirements.txt"
python3 -m venv "$zizmor_venv"
printf '%s\n' 'zizmor==1.28.0 --hash=sha256:ae2cab67ce713e760e0d1b61ad749d374693ea2b310337aab11cd446748267f3' > "$zizmor_requirements"
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
# with metrics explicitly disabled.
semgrep_venv="${RUNNER_TEMP:-/tmp}/semgrep-venv"
python3 -m venv "$semgrep_venv"
"$semgrep_venv/bin/python" -m pip install \
  --disable-pip-version-check \
  --no-input \
  "semgrep==1.170.0"
ln -sf "$semgrep_venv/bin/semgrep" "$BIN_DIR/semgrep"

echo "$BIN_DIR" >> "$GITHUB_PATH"
