#!/usr/bin/env python3
"""Contract tests for the audit-request resolver's safe, single-line outputs."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESOLVER = ROOT / ".audit/scripts/resolve_request.py"
BASE = dict(request_id="test-123", target_repo="Example/plugin",
            target_ref="main", target_path=".", run_runtime=True, php_version="8.3")


def invoke(changes=None, event="push", ref="runtime/test"):
    data = {**BASE, **(changes or {})}
    with tempfile.TemporaryDirectory() as temporary:
        request = Path(temporary) / "request.json"
        request.write_text(json.dumps(data), encoding="utf-8")
        env = os.environ.copy()
        env.update(EVENT_NAME=event, REF_NAME=ref, REQUEST_FILE=str(request),
                   GITHUB_RUN_ID="1234", INPUT_TARGET_REPO=str(data["target_repo"]),
                   INPUT_TARGET_REF=str(data["target_ref"]),
                   INPUT_TARGET_PATH=str(data["target_path"]),
                   INPUT_RUN_RUNTIME=str(data["run_runtime"]),
                   INPUT_PHP_VERSION=str(data["php_version"]))
        return subprocess.run([sys.executable, str(RESOLVER)], cwd=ROOT, env=env,
                              check=False, text=True, capture_output=True)


def main():
    positive = [
        ({}, "target-repo"),
        ({"target_path": "a/plugin"}, "target-repo/a/plugin"),
        ({"target_path": r"a\plugin"}, "target-repo/a/plugin"),
        ({"target_path": "./plugin/"}, "target-repo/plugin"),
        ({"target_path": "nested/long-name", "run_runtime": False}, "target-repo/nested/long-name"),
    ]
    for overrides, wanted in positive:
        proc = invoke(overrides)
        assert proc.returncode == 0, (overrides, proc.stderr)
        lines = proc.stdout.splitlines()
        assert len(lines) == 7, lines
        pairs = dict(line.split("=", 1) for line in lines)
        assert len(pairs) == 7 and pairs["plugin_dir"] == wanted, pairs

    check = invoke({"target_path": "plugin"}, event="workflow_dispatch")
    assert check.returncode == 0, check.stderr
    controls = [chr(value) for value in (0, 9, 10, 13, 31, 127, 133, 0x2028, 0x2029)]
    bad = [
        {"target_path": "../private"},
        {"target_path": "/absolute"},
        {"target_path": "a/../../outside"},
        {"target_repo": "invalid repo"},
        {"target_ref": "bad ref"},
        {"php_version": "invalid"},
        {"run_runtime": "unknown"},
    ]
    bad += [{"target_path": "plugin" + control + "name"} for control in controls]
    bad += [{"request_id": "test" + control + "id"} for control in controls]
    for overrides in bad:
        proc = invoke(overrides)
        assert proc.returncode == 2 and not proc.stdout, (
            overrides, proc.returncode, proc.stdout, proc.stderr
        )
    for kwargs in ({"ref": "main"}, {"event": "pull_request"}):
        proc = invoke(**kwargs)
        assert proc.returncode == 2 and not proc.stdout, kwargs
    print(f"audit request validation: OK ({len(positive)+1} valid, {len(bad)+2} rejected)")


if __name__ == "__main__":
    main()
