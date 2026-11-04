#!/usr/bin/env python3
"""Prepare a private, isolated theme+plugin release pair for wp-env.

No network, database access or execution of the submitted PHP code occurs here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import sys
import zipfile

MAX_FILES = 3000
MAX_UNCOMPRESSED = 512 * 1024 * 1024
SAFE_MEMBER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def extract_release(source: Path, destination: Path, kind: str) -> tuple[str, str]:
    """Fail closed on traversal, symbolic links, unexpected roots and missing headers."""
    if not source.is_file() or not zipfile.is_zipfile(source):
        raise ValueError(f"{kind}: not a readable ZIP")
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if not names or len(names) > MAX_FILES or len(set(names)) != len(names):
            raise ValueError(f"{kind}: invalid file count or duplicate entries")
        if sum(item.file_size for item in infos) > MAX_UNCOMPRESSED:
            raise ValueError(f"{kind}: excessive uncompressed size")
        roots = set()
        for item in infos:
            name = item.filename
            parts = name.rstrip("/").split("/")
            if (not SAFE_MEMBER.fullmatch(name.rstrip("/"))
                    or any(part in ("", ".", "..") for part in parts)
                    or len(parts) < 2
                    or (item.external_attr >> 16) & stat.S_IFMT(stat.S_IFLNK)):
                raise ValueError(f"{kind}: unsafe archive member")
            roots.add(parts[0])
            if item.flag_bits & 0x1:
                raise ValueError(f"{kind}: encrypted files are not accepted")
        if len(roots) != 1:
            raise ValueError(f"{kind}: archive requires one top-level directory")
        slug = next(iter(roots))
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
            raise ValueError(f"{kind}: invalid WordPress slug")
        entries = {name for name in names if not name.endswith("/")}
        if kind == "theme":
            if f"{slug}/style.css" not in entries:
                raise ValueError("theme: missing style.css")
            if b"Theme Name:" not in archive.read(f"{slug}/style.css"):
                raise ValueError("theme: missing Theme Name metadata")
        else:
            candidates = [name for name in entries if name.startswith(slug + "/")
                          and name.count("/") == 1 and name.endswith(".php")]
            if not any(b"Plugin Name:" in archive.read(name) for name in candidates):
                raise ValueError("plugin: missing bootstrap header")
        destination.mkdir(parents=True, exist_ok=True)
        archive.extractall(destination)
    return slug, hashlib.sha256(source.read_bytes()).hexdigest()


def prepare(args: argparse.Namespace) -> None:
    out = Path(args.output).resolve()
    if out.exists():
        raise ValueError("Output directory already exists; use a new isolated run")
    out.mkdir(parents=True)
    try:
        theme_slug, theme_hash = extract_release(Path(args.theme), out / "theme", "theme")
        plugin_slug, plugin_hash = extract_release(Path(args.plugin), out / "candidate", "plugin")
        upgrading = bool(args.previous_plugin)
        if upgrading:
            old_slug, old_hash = extract_release(
                Path(args.previous_plugin), out / "plugin", "plugin"
            )
            if old_slug != plugin_slug:
                raise ValueError("Previous plugin and candidate have different slugs")
        else:
            shutil.move(str(out / "candidate"), str(out / "plugin"))
            old_hash = None
        config = {
            "phpVersion": args.php,
            "themes": [f"./theme/{theme_slug}"],
            "plugins": [f"./plugin/{plugin_slug}"],
            "config": {
                "WP_DEBUG": True,
                "WP_DEBUG_LOG": True,
                "WP_DEBUG_DISPLAY": False,
            },
        }
        (out / ".wp-env.json").write_text(json.dumps(config, indent=2) + "\n")
        (out / "receipt.json").write_text(json.dumps({
            "theme_sha256": theme_hash, "plugin_sha256": plugin_hash,
            "previous_plugin_sha256": old_hash,
            "theme_slug": theme_slug, "plugin_slug": plugin_slug,
            "upgrade_mode": upgrading, "php": args.php,
        }, indent=2) + "\n")
    except Exception:
        shutil.rmtree(out)
        raise


def promote(output: Path) -> None:
    out = output.resolve()
    receipt = json.loads((out / "receipt.json").read_text())
    if not receipt["upgrade_mode"]:
        raise ValueError("Cannot promote without a previous plugin")
    slug = receipt["plugin_slug"]
    current = out / "plugin" / slug
    candidate = out / "candidate" / slug
    if not current.is_dir() or not candidate.is_dir():
        raise ValueError("Plugin sources not ready for promotion")
    shutil.rmtree(current)
    shutil.move(str(candidate), str(current))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    init = sub.add_parser("prepare")
    init.add_argument("--theme", required=True)
    init.add_argument("--plugin", required=True)
    init.add_argument("--previous-plugin")
    init.add_argument("--output", required=True)
    init.add_argument("--php", choices=("8.2", "8.3", "8.4"), default="8.3")
    upgrade = sub.add_parser("promote")
    upgrade.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        prepare(args) if args.mode == "prepare" else promote(Path(args.output))
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    main()
