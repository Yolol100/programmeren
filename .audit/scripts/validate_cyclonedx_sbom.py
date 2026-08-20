#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path


def validate(path: Path) -> tuple[str, int]:
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit("CycloneDX SBOM is missing or empty")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"CycloneDX SBOM is not valid JSON: {exc}") from exc

    if data.get("bomFormat") != "CycloneDX":
        raise SystemExit("SBOM bomFormat must be CycloneDX")

    spec_version = data.get("specVersion")
    if not isinstance(spec_version, str) or not spec_version:
        raise SystemExit("SBOM specVersion is missing")

    components = data.get("components")
    if components is not None and not isinstance(components, list):
        raise SystemExit("SBOM components must be a list when present")

    return spec_version, len(components or [])


def write_fingerprint(path: Path, fingerprint_path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    fingerprint_path.parent.mkdir(parents=True, exist_ok=True)
    fingerprint_path.write_text(f"{digest}  {path.as_posix()}\n", encoding="utf-8")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and fingerprint a CycloneDX JSON SBOM.")
    parser.add_argument("sbom", type=Path)
    parser.add_argument("--fingerprint", type=Path, required=True)
    args = parser.parse_args()

    spec_version, component_count = validate(args.sbom)
    digest = write_fingerprint(args.sbom, args.fingerprint)
    print(f"CycloneDX SBOM valid: spec={spec_version}, components={component_count}, sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
