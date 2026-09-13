#!/usr/bin/env python3
"""Fail-closed validation for deleting temporary runtime/** audit branches."""
from __future__ import annotations

import argparse
import json
import re

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
BRANCH_RE = re.compile(r"^runtime/[A-Za-z0-9._/-]+$")


def validate(branch: str, expected_sha: str, current_sha: str) -> None:
    if not BRANCH_RE.fullmatch(branch):
        raise ValueError("branch must stay inside the runtime/** namespace")
    if branch.endswith("/") or "//" in branch:
        raise ValueError("branch contains an empty path segment")
    tail = branch.removeprefix("runtime/")
    parts = tail.split("/")
    if not tail or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("branch contains an unsafe path segment")
    if not SHA_RE.fullmatch(expected_sha):
        raise ValueError("expected source-run SHA must be a lowercase 40-hex commit")
    if not SHA_RE.fullmatch(current_sha):
        raise ValueError("current branch SHA must be a lowercase 40-hex commit")
    if expected_sha != current_sha:
        raise ValueError("runtime branch moved after the audited run; refusing deletion")


def self_test() -> None:
    good = "a" * 40
    validate("runtime/audit-20260913", good, good)
    validate("runtime/nested/audit_01.test", good, good)
    bad_cases = [
        ("main", good, good),
        ("runtime/", good, good),
        ("runtime/../main", good, good),
        ("runtime/a//b", good, good),
        ("runtime/a b", good, good),
        ("runtime/a", "A" * 40, good),
        ("runtime/a", good, "b" * 40),
        ("runtime/a", good[:-1], good),
    ]
    for branch, expected, current in bad_cases:
        try:
            validate(branch, expected, current)
        except ValueError:
            continue
        raise AssertionError(f"unsafe cleanup case unexpectedly passed: {branch!r}")
    print("runtime-branch-cleanup-guard: self-test PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch")
    parser.add_argument("--expected-sha")
    parser.add_argument("--current-sha")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0
    if not all((args.branch, args.expected_sha, args.current_sha)):
        parser.error("--branch, --expected-sha and --current-sha are required unless --self-test is used")
    try:
        validate(args.branch, args.expected_sha, args.current_sha)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({"ok": True, "branch": args.branch, "sha": args.current_sha}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
