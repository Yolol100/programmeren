#!/usr/bin/env python3
"""Verify an audit receipt, its provenance and every downloaded evidence byte.

Use only on an extracted set of artifacts from the same trusted GitHub Actions run.
The validator accepts an honestly failed source audit; this is evidence integrity,
not an audit pass/fail override.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")


def fail(message: str) -> None:
    raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(evidence_dir: Path, receipt_dir: Path, run_id: str,
           harness_sha: str, source_conclusion: str,
           target_sha: str | None = None, target_repo: str | None = None) -> int:
    if not SHA_RE.fullmatch(harness_sha):
        fail("Invalid expected harness commit")
    if not run_id.isdigit():
        fail("Invalid expected workflow run ID")
    if not evidence_dir.is_dir() or not receipt_dir.is_dir():
        fail("Missing evidence or receipt directory")

    receipt_path = receipt_dir / "result-receipt.json"
    index_path = receipt_dir / "evidence-index.json"
    if not receipt_path.is_file() or not index_path.is_file():
        fail("Missing receipt or evidence index")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict) or not isinstance(index, dict):
        fail("Receipt and evidence index must be objects")
    if receipt.get("schema_version") != "1.0" or index.get("schema_version") != "1.0":
        fail("Unsupported evidence schema version")
    if receipt.get("run_id") != run_id or receipt.get("harness_commit") != harness_sha:
        fail("Receipt is not bound to the expected workflow run and commit")
    if receipt.get("source_conclusion") != source_conclusion:
        fail("Source audit conclusion differs from expected event")
    if receipt.get("status") not in {"completed", "failed", "blocked", "cancelled"}:
        fail("Invalid receipt terminal status")
    if source_conclusion != "success" and receipt.get("status") == "completed":
        fail("Failed source run cannot have a completed receipt")

    source = index.get("source_run", {})
    if not isinstance(source, dict):
        fail("Missing indexed run provenance")
    expected_source = {
        "run_id": run_id,
        "run_attempt": receipt.get("run_attempt"),
        "conclusion": source_conclusion,
        "harness_repository": receipt.get("harness_repository"),
        "harness_commit": harness_sha,
        "request_id": receipt.get("request_id"),
        "target_repository": receipt.get("target_repository"),
        "target_ref": receipt.get("target_ref"),
        "target_commit": receipt.get("target_commit"),
        "target_path": receipt.get("target_path"),
        "profile": receipt.get("profile"),
    }
    for key, expected in expected_source.items():
        if source.get(key) != expected:
            fail(f"Index and receipt disagree on {key}")
    if not SHA_RE.fullmatch(str(receipt.get("target_commit") or "")):
        fail("Missing or invalid target commit")
    if target_sha is not None and receipt["target_commit"] != target_sha:
        fail("Receipt does not match the expected target commit")
    if target_repo is not None and receipt.get("target_repository") != target_repo:
        fail("Receipt does not match the expected target repository")
    builder = index.get("receipt_builder", {})
    if not isinstance(builder, dict) or builder.get("commit") != receipt.get("receipt_builder_commit") \
            or builder.get("repository") != receipt.get("receipt_builder_repository"):
        fail("Receipt builder provenance mismatch")
    if not SHA_RE.fullmatch(str(receipt.get("receipt_builder_commit") or "")):
        fail("Invalid trusted receipt builder commit")

    reference = receipt.get("evidence_index", {})
    if not isinstance(reference, dict) or reference.get("path") != "evidence-index.json":
        fail("Receipt points to an invalid evidence index")
    expected_index_digest = reference.get("sha256")
    if not isinstance(expected_index_digest, str) or not SHA256_RE.fullmatch(expected_index_digest):
        fail("Invalid evidence index fingerprint")
    if sha256(index_path) != expected_index_digest:
        fail("Evidence index changed after receipt was created")
    records = index.get("files")
    if not isinstance(records, list) or not records:
        fail("Evidence index is empty or malformed")
    if index.get("file_count") != len(records) or reference.get("file_count") != len(records):
        fail("Evidence file count mismatch")

    root = evidence_dir.resolve(strict=True)
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            fail("Invalid evidence record")
        name = record.get("path")
        digest = record.get("sha256")
        size = record.get("size_bytes")
        if not isinstance(name, str) or "\\" in name or not name:
            fail("Invalid evidence path")
        part = PurePosixPath(name)
        if part.is_absolute() or ".." in part.parts or part.as_posix() != name or name in seen:
            fail("Unsafe or duplicate evidence path")
        seen.add(name)
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            fail(f"Invalid digest for {name}")
        if type(size) is not int or size < 0:
            fail(f"Invalid evidence size for {name}")
        candidate = root.joinpath(*part.parts)
        if candidate.is_symlink() or not candidate.is_file() or not candidate.resolve().is_relative_to(root):
            fail(f"Missing, symlinked, or outside-root evidence file: {name}")
        if candidate.stat().st_size != size or sha256(candidate) != digest:
            fail(f"Evidence size or SHA-256 mismatch: {name}")

    actual = {f.relative_to(root).as_posix() for f in root.rglob("*") if f.is_file()}
    if actual != seen:
        fail("Unindexed or missing files exist in evidence directory")
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--receipt-dir", required=True, type=Path)
    parser.add_argument("--expected-run-id", required=True)
    parser.add_argument("--expected-harness-sha", required=True)
    parser.add_argument("--expected-conclusion", required=True)
    parser.add_argument("--expected-target-sha")
    parser.add_argument("--expected-target-repo")
    args = parser.parse_args()
    try:
        count = verify(args.evidence_dir, args.receipt_dir, args.expected_run_id,
                       args.expected_harness_sha, args.expected_conclusion,
                       args.expected_target_sha, args.expected_target_repo)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"Evidence receipt verification FAILED: {error}", file=sys.stderr)
        return 2
    print(f"Evidence receipt verification OK: {count} files, run={args.expected_run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
