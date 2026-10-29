#!/usr/bin/env python3
"""Networkless security regression for the exact-version Composer bootstrap."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / ".audit/scripts/install_pinned_composer.sh"
SHA = "7a2d379d5b8ffdaa028580ef26494c36d2feef4b178d3dd1473a4dbc5e17c8d6"


def validate_source(source):
    required = (
        'COMPOSER_VERSION="2.10.3"',
        f'COMPOSER_SHA256="{SHA}"',
        'getcomposer.org/download/${COMPOSER_VERSION}/composer.phar',
        'sha256sum -c -',
        'install -m 0755',
        'ACTUAL_VERSION',
    )
    return all(marker in source for marker in required) and source.count("sha256sum -c -") == 2


def main():
    content = BOOTSTRAP.read_text(encoding="utf-8")
    assert validate_source(content), "composer bootstrap must retain exact version and two SHA checks"
    for broken in (content.replace(SHA, "0" * 64), content.replace("2.10.3", "2.11.0"),
                   content.replace("sha256sum -c -", "cat >/dev/null")):
        assert not validate_source(broken), "a mutated pin or missing SHA gate must be rejected"

    for name in ("full-plugin-audit.yml", "toolkit-contract.yml"):
        workflow = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        assert "tools: none" in workflow, name
        assert "bash .audit/scripts/install_pinned_composer.sh" in workflow, name
        bootstrap_prefix = workflow.split("      - name: Bootstrap pinned Composer", 1)[0]
        assert "tools: composer:v2" not in bootstrap_prefix and "tools: composer:2.10.3@" not in bootstrap_prefix, name

    with TemporaryDirectory() as temporary:
        tmp = Path(temporary)
        bin_dir = tmp / "stub"
        bin_dir.mkdir()
        fake_curl = bin_dir / "curl"
        fake_curl.write_text('''#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then shift; out="$1"; fi
  shift
done
printf 'tampered composer archive' > "$out"
''', encoding="utf-8")
        fake_curl.chmod(0o755)
        environment = os.environ.copy()
        environment.update(RUNNER_TEMP=str(tmp), GITHUB_PATH=str(tmp / "github_path"),
                           PATH=str(bin_dir) + os.pathsep + environment["PATH"])
        process = subprocess.run(["bash", str(BOOTSTRAP)], capture_output=True, text=True,
                                 check=False, env=environment, timeout=10)
        assert process.returncode != 0 and "FAILED" in process.stdout + process.stderr, (
            process.returncode, process.stdout, process.stderr)
        assert not (tmp / "webactueel-pinned-composer-bin" / "composer").exists(), (
            "unverified download must never install as composer")
        assert not (tmp / "github_path").exists(), "failed bootstrap must not append to GITHUB_PATH"

    print("Pinned Composer bootstrap: PASS (source invariants, mutations, invalid-SHA execution)")


if __name__ == "__main__":
    main()
