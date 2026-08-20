#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

TARGET_DEPENDENCY_FILES = (
    "composer.json",
    "composer.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
)

HARNESS_DEPENDENCY_FILES = (
    ".audit/tools/composer.json",
    ".audit/tools/composer.lock",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect(root: Path, relative_paths: tuple[str, ...], scope: str) -> tuple[list[dict[str, object]], list[str]]:
    files: list[dict[str, object]] = []
    missing: list[str] = []
    for relative in relative_paths:
        path = root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        files.append({
            "scope": scope,
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return files, missing


def build_report(target_root: Path, harness_root: Path, repository: str, ref: str, commit: str) -> dict[str, object]:
    target_files, target_missing = collect(target_root, TARGET_DEPENDENCY_FILES, "target")
    harness_files, harness_missing = collect(harness_root, HARNESS_DEPENDENCY_FILES, "audit_harness")
    return {
        "schema_version": "1.0",
        "algorithm": "sha256",
        "target": {"repository": repository, "ref": ref, "commit": commit},
        "files": target_files + harness_files,
        "missing": {
            "target": target_missing,
            "audit_harness": harness_missing,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Write deterministic dependency-manifest and lockfile provenance for a plugin audit.")
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--harness-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()

    report = build_report(args.target_root.resolve(), args.harness_root.resolve(), args.repository, args.ref, args.commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"dependency_provenance_files={len(report['files'])} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
