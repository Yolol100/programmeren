#!/usr/bin/env python3
"""Regression checks for fail-closed audit receipt classification."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("build-evidence-receipt.py")
spec = importlib.util.spec_from_file_location("build_evidence_receipt", MODULE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("Unable to load build-evidence-receipt.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

cases = [
    ("success", True, ("completed", None)),
    ("success", False, ("failed", "NO_EVIDENCE_ARTIFACTS")),
    ("failure", True, ("failed", "AUDIT_RUN_FAILURE")),
    ("cancelled", True, ("cancelled", "AUDIT_RUN_CANCELLED")),
    ("neutral", True, ("blocked", "AUDIT_RUN_NEUTRAL")),
    ("skipped", True, ("blocked", "AUDIT_RUN_SKIPPED")),
    ("unexpected-state", True, ("blocked", "AUDIT_RUN_UNEXPECTED_STATE")),
]

for conclusion, has_evidence, expected in cases:
    actual = module.classify_status(conclusion, has_evidence)
    assert actual == expected, (conclusion, has_evidence, actual, expected)

print(f"evidence receipt classification: OK ({len(cases)} cases)")


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    evidence = root / "evidence"
    evidence.mkdir()
    (evidence / "artifact.txt").write_text("proof\n", encoding="utf-8")
    output = root / "receipt"
    source_sha = "a" * 40
    builder_sha = "b" * 40
    subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--evidence-dir", str(evidence),
            "--run-id", "123",
            "--run-attempt", "1",
            "--run-conclusion", "success",
            "--harness-repo", "Yolol100/programmeren",
            "--harness-sha", source_sha,
            "--receipt-builder-sha", builder_sha,
            "--output-dir", str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    receipt = json.loads((output / "result-receipt.json").read_text(encoding="utf-8"))
    index = json.loads((output / "evidence-index.json").read_text(encoding="utf-8"))
    assert receipt["harness_commit"] == source_sha
    assert receipt["receipt_builder_commit"] == builder_sha
    assert index["source_run"]["harness_commit"] == source_sha
    assert index["receipt_builder"]["commit"] == builder_sha
    assert source_sha != builder_sha

print("evidence receipt provenance: OK")


def invoke_receipt_fixture(summary_text):
    """Return a receipt produced from downloaded-style audit evidence."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        evidence = root / "evidence"
        evidence.mkdir()
        (evidence / "artifact.txt").write_text("proof\n", encoding="utf-8")
        if summary_text is not None:
            (evidence / "SUMMARY.md").write_text(summary_text, encoding="utf-8")
        output = root / "receipt"
        result = subprocess.run([
            sys.executable, str(MODULE_PATH),
            "--evidence-dir", str(evidence),
            "--run-id", "321",
            "--run-attempt", "1",
            "--run-conclusion", "success",
            "--harness-repo", "Yolol100/programmeren",
            "--harness-sha", "a" * 40,
            "--receipt-builder-sha", "b" * 40,
            "--output-dir", str(output),
        ], check=False, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return json.loads((output / "result-receipt.json").read_text(encoding="utf-8"))


tick = chr(96)
fields = {
    "request_id": "audit-321",
    "repository": "Acme/sample-plugin",
    "ref": "main",
    "commit": "c" * 40,
    "path": ".",
    "profile": "base",
}
full_summary = "# WordPress Plugin Audit\n\n" + "".join(
    f"- {key}: {tick}{value}{tick}\n" for key, value in fields.items()
)
cases = [
    ("complete summary", full_summary, "completed", None),
    ("summary missing", None, "failed", "INCOMPLETE_AUDIT_PROVENANCE"),
    ("empty summary", "", "failed", "INCOMPLETE_AUDIT_PROVENANCE"),
    ("missing repository", full_summary.replace(f"- repository: {tick}Acme/sample-plugin{tick}\n", ""),
     "failed", "INCOMPLETE_AUDIT_PROVENANCE"),
    ("invalid commit", full_summary.replace("c" * 40, "not-a-sha"),
     "failed", "INCOMPLETE_AUDIT_PROVENANCE"),
    ("empty request", full_summary.replace(f"- request_id: {tick}audit-321{tick}",
                                          f"- request_id: {tick}{tick}"),
     "failed", "INCOMPLETE_AUDIT_PROVENANCE"),
]
for name, summary_text, status, error in cases:
    receipt = invoke_receipt_fixture(summary_text)
    assert (receipt["status"], receipt["error_code"]) == (status, error), (
        name, receipt["status"], receipt["error_code"], status, error
    )
print(f"audit receipt identity provenance: OK ({len(cases)} cases)")
