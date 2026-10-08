#!/usr/bin/env python3
"""Behavioral boundary tests for the public audit harness's target visibility gate."""
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".audit/scripts/check_target_visibility.sh"


def check(metadata, expected, harness="public", api_error=False):
    with tempfile.TemporaryDirectory(prefix="audit-visibility-test-") as tmp:
        stub = Path(tmp) / "curl"
        stub.write_text(
            '#!/usr/bin/env bash\n'
            'if [[ "$MOCK_CURL_FAIL" == "1" ]]; then exit 22; fi\n'
            'printf "%s\\n" "$MOCK_METADATA"\n',
            encoding="utf-8",
        )
        stub.chmod(0o755)
        env = os.environ.copy()
        env.update(
            PATH=tmp + os.pathsep + env.get("PATH", ""),
            TARGET_REPO="Example/plugin",
            HARNESS_VISIBILITY=harness,
            MOCK_METADATA=metadata if isinstance(metadata, str) else json.dumps(metadata),
            MOCK_CURL_FAIL="1" if api_error else "0",
        )
        env.pop("GH_TOKEN", None)
        env.pop("PLUGIN_REPO_TOKEN", None)
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if expected is None:
            assert result.returncode != 0, (metadata, result.stdout, result.stderr)
        else:
            assert result.returncode == expected, (
                metadata, harness, expected, result.returncode, result.stdout, result.stderr
            )


def main():
    cases = [
        ({"private": False, "visibility": "public"}, 0, "public"),
        ({"private": True, "visibility": "private"}, 3, "public"),
        ({"private": False, "visibility": "internal"}, 3, "public"),
        ({"private": True, "visibility": "internal"}, 3, "public"),
        ({"private": False, "visibility": "private"}, 3, "public"),
        ({"private": True, "visibility": "public"}, 3, "public"),
        ({"private": False}, 3, "public"),
        ({"private": False, "visibility": "unknown"}, 3, "public"),
        ({"visibility": "public"}, 3, "public"),
        ({"private": None, "visibility": "public"}, 3, "public"),
        ({"private": "false", "visibility": "public"}, 3, "public"),
        ({"private": False, "visibility": "public"}, 3, "unknown"),
        ({"private": True, "visibility": "private"}, 0, "private"),
    ]
    for meta, expected, harness in cases:
        check(meta, expected, harness)
    check("{not-json", None)
    check({"private": False, "visibility": "public"}, None, api_error=True)
    print(f"target visibility boundary: OK ({len(cases) + 2} scenarios)")


if __name__ == "__main__":
    main()
