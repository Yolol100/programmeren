#!/usr/bin/env python3
"""Prevent distributing raw target source in a public audit's evidence artifact."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
static = (ROOT / ".audit/scripts/run_static_audit.sh").read_text(encoding="utf-8")
workflow = (ROOT / ".github/workflows/full-plugin-audit.yml").read_text(encoding="utf-8")

# Raw checkout archives can include untracked files injected during CI, even when
# a secret scanner reports findings. Keep immutable commit/provenance evidence only.
assert "source-snapshot.zip" not in static, "raw plugin snapshot may be uploaded"
assert "source-snapshot.sha256" not in static, "obsolete raw-source archive hash"
assert re.search(r"(?m)^\s*(?:zip|tar|7z)\s", static) is None, "raw source archiver in static audit"
assert "dependency-provenance.json" in static, "target dependency provenance must remain"
assert "commit=$TARGET_SHA" in static, "immutable target commit must remain"
assert "path: audit-results/" in workflow, "evidence upload path drift"
assert "path: target-repo" not in workflow, "target checkout must never be uploaded"

print("audit evidence payload hygiene: OK")
