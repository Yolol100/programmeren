#!/usr/bin/env python3
"""Regression checks for fail-closed audit receipt classification."""
from __future__ import annotations

import importlib.util
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
