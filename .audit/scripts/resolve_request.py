#!/usr/bin/env python3
import os
import re
import sys
from pathlib import PurePosixPath

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REF_RE = re.compile(r"^[A-Za-z0-9._/@+-]+$")
PHP_RE = re.compile(r"^(?:7\.[4-9]|8\.[0-9])$")


def fail(message: str) -> None:
    print(f"request error: {message}", file=sys.stderr)
    raise SystemExit(2)


def bool_value(value, default=True):
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    fail(f"invalid boolean value: {value!r}")


def clean_path(value: str) -> str:
    value = (value or ".").strip().replace("\\", "/")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        fail("target_path must be relative and may not contain '..'")
    return str(path)


def main() -> None:
    event = os.environ.get("EVENT_NAME", "")
    if event != "workflow_dispatch":
        fail("audit requests must use workflow_dispatch; default-branch request files are forbidden")

    data = {
        "request_id": os.environ.get("GITHUB_RUN_ID", "manual"),
        "target_repo": os.environ.get("INPUT_TARGET_REPO", ""),
        "target_ref": os.environ.get("INPUT_TARGET_REF", "main"),
        "target_path": os.environ.get("INPUT_TARGET_PATH", "."),
        "run_runtime": os.environ.get("INPUT_RUN_RUNTIME", "true"),
        "php_version": os.environ.get("INPUT_PHP_VERSION", "8.3"),
    }

    target_repo = str(data.get("target_repo", "")).strip()
    target_ref = str(data.get("target_ref", "main")).strip()
    target_path = clean_path(str(data.get("target_path", ".")))
    php_version = str(data.get("php_version", "8.3")).strip()
    run_runtime = bool_value(data.get("run_runtime", True), True)
    request_id = str(data.get("request_id", "request")).strip()

    if not REPO_RE.fullmatch(target_repo):
        fail("target_repo must be owner/repository")
    if not target_ref or not REF_RE.fullmatch(target_ref):
        fail("target_ref contains unsupported characters")
    if not PHP_RE.fullmatch(php_version):
        fail("php_version must look like 7.4 or 8.x")
    if not request_id or "\n" in request_id or "\r" in request_id:
        fail("request_id is invalid")

    outputs = {
        "request_id": request_id,
        "target_repo": target_repo,
        "target_ref": target_ref,
        "target_path": target_path,
        "run_runtime": "true" if run_runtime else "false",
        "php_version": php_version,
        "plugin_dir": f"target-repo/{target_path}" if target_path != "." else "target-repo",
    }
    for key, value in outputs.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
