#!/usr/bin/env python3
"""Build compact, hash-bound evidence index and result receipt for a completed audit run."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

FIELD_RE = re.compile(r"^- ([a-zA-Z0-9_]+): `([^`]*)`$", re.MULTILINE)
CONCLUSION_STATUS = {
    "success": "completed",
    "failure": "failed",
    "cancelled": "cancelled",
    "timed_out": "failed",
    "action_required": "blocked",
    "neutral": "completed",
    "skipped": "blocked",
    "stale": "blocked",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_summary_fields(root: Path) -> dict[str, str]:
    candidates = sorted(root.rglob("SUMMARY.md"))
    if not candidates:
        return {}
    text = candidates[0].read_text(encoding="utf-8", errors="replace")
    return {m.group(1): m.group(2) for m in FIELD_RE.finditer(text)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-dir", type=Path, required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--run-attempt", required=True)
    ap.add_argument("--run-conclusion", required=True)
    ap.add_argument("--harness-repo", required=True)
    ap.add_argument("--harness-sha", required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()

    evidence_dir = args.evidence_dir.resolve()
    files = []
    if evidence_dir.is_dir():
        for path in sorted(p for p in evidence_dir.rglob("*") if p.is_file()):
            files.append({
                "path": path.relative_to(evidence_dir).as_posix(),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            })

    summary = read_summary_fields(evidence_dir) if evidence_dir.is_dir() else {}
    evidence_index = {
        "schema_version": "1.0",
        "source_run": {
            "run_id": str(args.run_id),
            "run_attempt": str(args.run_attempt),
            "conclusion": args.run_conclusion,
            "harness_repository": args.harness_repo,
            "harness_commit": args.harness_sha,
            "request_id": summary.get("request_id"),
            "target_repository": summary.get("repository"),
            "target_ref": summary.get("ref"),
            "target_commit": summary.get("commit"),
            "target_path": summary.get("path"),
            "profile": summary.get("profile"),
        },
        "files": files,
        "file_count": len(files),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    index_path = args.output_dir / "evidence-index.json"
    write_json(index_path, evidence_index)

    status = CONCLUSION_STATUS.get(args.run_conclusion, "blocked")
    error_code = None
    if not files:
        status = "failed" if status == "completed" else status
        error_code = "NO_EVIDENCE_ARTIFACTS"
    elif status != "completed":
        error_code = "AUDIT_RUN_" + re.sub(r"[^A-Z0-9]+", "_", args.run_conclusion.upper()).strip("_")

    receipt = {
        "schema_version": "1.0",
        "run_id": str(args.run_id),
        "run_attempt": str(args.run_attempt),
        "status": status,
        "harness_repository": args.harness_repo,
        "harness_commit": args.harness_sha,
        "request_id": summary.get("request_id"),
        "target_repository": summary.get("repository"),
        "target_ref": summary.get("ref"),
        "target_commit": summary.get("commit"),
        "target_path": summary.get("path"),
        "profile": summary.get("profile"),
        "evidence_index": {
            "path": "evidence-index.json",
            "sha256": sha256_file(index_path),
            "file_count": len(files),
        },
        "error_code": error_code,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(args.output_dir / "result-receipt.json", receipt)
    print(json.dumps({"status": status, "file_count": len(files), "error_code": error_code}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
