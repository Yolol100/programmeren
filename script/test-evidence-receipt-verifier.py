#!/usr/bin/env python3
"""Positive and negative test vectors for the downloaded audit receipt verifier."""
import copy
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
module_spec = importlib.util.spec_from_file_location("verify_audit_evidence", HERE / "verify-evidence-receipt.py")
module = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(module)

RUN = "12345"
HARNESS = "a" * 40
BUILDER = "b" * 40
TARGET = "c" * 40


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def make_fixture(root: Path, status="failed", conclusion="failure"):
    evidence = root / "evidence"
    receipts = root / "receipt"
    evidence.mkdir()
    receipts.mkdir()
    (evidence / "audit").mkdir()
    file_path = evidence / "audit" / "sample.txt"
    file_path.write_bytes(b"verified audit data\n")
    source = {
        "run_id": RUN, "run_attempt": "1", "conclusion": conclusion,
        "harness_repository": "Yolol100/programmeren", "harness_commit": HARNESS,
        "request_id": "test-run", "target_repository": "Yolol100/wordpressconnector",
        "target_ref": TARGET, "target_commit": TARGET,
        "target_path": "plugin/wordpressconnector", "profile": "base",
    }
    index = {
        "schema_version": "1.0", "source_run": source,
        "receipt_builder": {"repository": "Yolol100/programmeren", "commit": BUILDER},
        "files": [{"path": "audit/sample.txt", "size_bytes": file_path.stat().st_size,
                   "sha256": digest(file_path.read_bytes())}], "file_count": 1,
    }
    index_path = receipts / "evidence-index.json"
    write_json(index_path, index)
    receipt = {
        "schema_version": "1.0", "run_id": RUN, "run_attempt": "1",
        "status": status, "source_conclusion": conclusion,
        "harness_repository": "Yolol100/programmeren", "harness_commit": HARNESS,
        "receipt_builder_repository": "Yolol100/programmeren", "receipt_builder_commit": BUILDER,
        "request_id": "test-run", "target_repository": "Yolol100/wordpressconnector",
        "target_ref": TARGET, "target_commit": TARGET,
        "target_path": "plugin/wordpressconnector", "profile": "base",
        "evidence_index": {"path": "evidence-index.json", "sha256": digest(index_path.read_bytes()),
                           "file_count": 1},
    }
    write_json(receipts / "result-receipt.json", receipt)
    return evidence, receipts, receipt, index


def check(e, r, h=HARNESS, conclusion="failure"):
    return module.verify(e, r, RUN, h, conclusion)


def expect_fail(label, mutate, *, update_hash=False):
    with tempfile.TemporaryDirectory() as t:
        e, r, receipt, index = make_fixture(Path(t))
        mutate(e, r, receipt, index)
        if update_hash:
            write_json(r / "evidence-index.json", index)
            receipt["evidence_index"]["sha256"] = digest((r / "evidence-index.json").read_bytes())
            write_json(r / "result-receipt.json", receipt)
        try:
            check(e, r)
        except (ValueError, OSError, json.JSONDecodeError):
            print("Rejected:", label)
            return
        raise AssertionError("Not rejected: " + label)


for status, conclusion in [("failed", "failure"), ("completed", "success")]:
    with tempfile.TemporaryDirectory() as t:
        e, r, _, _ = make_fixture(Path(t), status, conclusion)
        assert module.verify(e, r, RUN, HARNESS, conclusion) == 1
        print("Verified:", status, conclusion)

expect_fail("file tampering", lambda e, r, rc, ix: (e / "audit" / "sample.txt").write_bytes(b"tampered\n"))
expect_fail("index tampering", lambda e, r, rc, ix: (r / "evidence-index.json").write_bytes(b"{}\n"))
expect_fail("source run discrepancy", lambda e, r, rc, ix: rc.update({"run_id": "different"}) or write_json(r / "result-receipt.json", rc))
expect_fail("harness SHA discrepancy", lambda e, r, rc, ix: rc.update({"harness_commit": "d"*40}) or write_json(r / "result-receipt.json", rc))
expect_fail("failed run wrongly completed", lambda e, r, rc, ix: rc.update({"status": "completed"}) or write_json(r / "result-receipt.json", rc))
expect_fail("unindexed extra evidence", lambda e, r, rc, ix: (e / "extra.txt").write_text("extra", encoding="utf-8"))
expect_fail("missing evidence", lambda e, r, rc, ix: (e / "audit" / "sample.txt").unlink())
expect_fail("path traversal", lambda e, r, rc, ix: ix["files"][0].update({"path": "../secret.txt"}), update_hash=True)
expect_fail("duplicate indexed entry", lambda e, r, rc, ix: ix["files"].append(copy.deepcopy(ix["files"][0])) or ix.update({"file_count": 2}) or rc["evidence_index"].update({"file_count": 2}),update_hash=True)
expect_fail("incorrect index source identity", lambda e, r, rc, ix: ix["source_run"].update({"target_commit": "d"*40}), update_hash=True)
expect_fail("malformed index digest", lambda e, r, rc, ix: rc["evidence_index"].update({"sha256": "bogus"}) or write_json(r / "result-receipt.json", rc))
with tempfile.TemporaryDirectory() as t:
    e, r, _, _ = make_fixture(Path(t))
    try:
        module.verify(e, r, RUN, HARNESS, "failure", "d" * 40, "Yolol100/wordpressconnector")
        raise AssertionError("Wrong target SHA unexpectedly accepted")
    except ValueError:
        print("Rejected: external target SHA mismatch")
    assert module.verify(e, r, RUN, HARNESS, "failure", TARGET, "Yolol100/wordpressconnector") == 1

print("audit evidence receipt verifier: OK (3 positive; 12 negative cases)")
