#!/usr/bin/env python3
"""Behavioral lifecycle and fail-closed tests for the generic wp-env runtime probe."""
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".audit/scripts/runtime_probe.sh"
WP_ENV = r"""#!/usr/bin/env bash
case "$*" in
  *"config set "*) exit "$MOCK_CONFIG_FAIL" ;;
  *"plugin deactivate "*) exit "$MOCK_DEACTIVATE_FAIL" ;;
  *"plugin activate "*) exit "$MOCK_ACTIVATE_FAIL" ;;
  *"bash -lc "*) 
    if [[ "$MOCK_DEBUG_FATAL" == "1" ]]; then echo "PHP Fatal error: test fixture"; fi
    if [[ "$MOCK_DEBUG_MEMORY" == "1" ]]; then echo "Allowed memory size of 100 bytes exhausted"; fi
    if [[ "$MOCK_DEBUG_WARNING" == "1" ]]; then echo "PHP Warning: nonfatal test fixture"; fi
    exit "$MOCK_DEBUG_READ_FAIL" ;;
esac
exit 0
"""
CURL = r"""#!/usr/bin/env bash
if [[ "$*" == *"/wp-json/"* ]]; then exit "$MOCK_REST_FAIL"; fi
exit "$MOCK_HOME_FAIL"
"""
STATUS_KEYS = {
    "config_wp_debug_exit",
    "config_wp_debug_log_exit",
    "config_wp_debug_display_exit",
    "deactivate_exit",
    "activate_exit",
    "home_exit",
    "rest_exit",
    "debug_read_exit",
}


def check(overrides, expected, slug="test-plugin"):
    with tempfile.TemporaryDirectory(prefix="audit-runtime-test-") as tmp:
        base = Path(tmp)
        bin_dir = base / "bin"
        bin_dir.mkdir()
        for filename, content in (("wp-env", WP_ENV), ("curl", CURL)):
            stub = bin_dir / filename
            stub.write_text(content, encoding="utf-8")
            stub.chmod(0o755)
        env = os.environ.copy()
        env.update(
            PATH=str(bin_dir) + os.pathsep + env.get("PATH", ""),
            GITHUB_WORKSPACE=str(base),
            PLUGIN_SLUG=slug,
            MOCK_CONFIG_FAIL="0",
            MOCK_DEACTIVATE_FAIL="0",
            MOCK_ACTIVATE_FAIL="0",
            MOCK_HOME_FAIL="0",
            MOCK_REST_FAIL="0",
            MOCK_DEBUG_READ_FAIL="0",
            MOCK_DEBUG_FATAL="0",
            MOCK_DEBUG_MEMORY="0",
            MOCK_DEBUG_WARNING="0",
        )
        env.update(overrides)
        proc = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert proc.returncode == expected, (
            overrides, slug, expected, proc.returncode, proc.stdout, proc.stderr
        )
        if slug:
            status_file = base / "audit-results/runtime-status.txt"
            assert status_file.is_file(), (overrides, proc.stdout, proc.stderr)
            pairs = dict(line.split("=", 1) for line in status_file.read_text().splitlines())
            assert STATUS_KEYS <= pairs.keys(), (overrides, pairs)
        else:
            assert not (base / "audit-results/runtime-status.txt").exists()


def main():
    cases = [
        ({}, 0),
        ({"MOCK_DEBUG_WARNING": "1"}, 0),
        ({"MOCK_CONFIG_FAIL": "1"}, 1),
        ({"MOCK_DEACTIVATE_FAIL": "1"}, 1),
        ({"MOCK_ACTIVATE_FAIL": "1"}, 1),
        ({"MOCK_HOME_FAIL": "1"}, 1),
        ({"MOCK_REST_FAIL": "1"}, 1),
        ({"MOCK_DEBUG_READ_FAIL": "1"}, 1),
        ({"MOCK_DEBUG_FATAL": "1"}, 1),
        ({"MOCK_DEBUG_MEMORY": "1"}, 1),
    ]
    for overrides, expected in cases:
        check(overrides, expected)
    check({}, 2, slug="")
    print(f"WordPress runtime lifecycle: OK ({len(cases)+1} scenarios)")


if __name__ == "__main__":
    main()
