#!/usr/bin/env python3
"""No-network contract tests for private WordPress release-pair preparation."""
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
import zipfile

MODULE_PATH = Path(__file__).with_name("release-pair-prepare.py")
SPEC = importlib.util.spec_from_file_location("pair_prepare", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_zip(path, slug, kind, marker="one", extra=None):
    header = ("/*\nTheme Name: Test\n*/" if kind == "theme"
              else "<?php\n/*\nPlugin Name: Test\n*/")
    name = "style.css" if kind == "theme" else "test-plugin.php"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{slug}/{name}", header)
        archive.writestr(f"{slug}/marker.txt", marker)
        for item, data in extra or []:
            archive.writestr(item, data)


class ZipReleasePairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.theme = self.base / "theme.zip"
        self.plugin = self.base / "plugin.zip"
        self.out = self.base / "out"
        write_zip(self.theme, "sample-theme", "theme")
        write_zip(self.plugin, "sample-plugin", "plugin")

    def args(self, old=None):
        return MODULE.argparse.Namespace(theme=str(self.theme),
            plugin=str(self.plugin), previous_plugin=str(old) if old else None,
            output=str(self.out), php="8.3")

    def test_clean_pair_builds_config_and_hashes(self):
        MODULE.prepare(self.args())
        config = json.loads((self.out / ".wp-env.json").read_text())
        receipt = json.loads((self.out / "receipt.json").read_text())
        self.assertEqual(config["themes"], ["./theme/sample-theme"])
        self.assertEqual(config["plugins"], ["./plugin/sample-plugin"])
        self.assertEqual(receipt["theme_sha256"], MODULE.hashlib.sha256(self.theme.read_bytes()).hexdigest())
        self.assertFalse(receipt["upgrade_mode"])
        self.assertTrue((self.out / "plugin/sample-plugin/test-plugin.php").exists())

    def test_upgrade_promotes_without_replacing_mount_directory(self):
        old = self.base / "previous.zip"
        write_zip(old, "sample-plugin", "plugin", marker="old",
                  extra=[("sample-plugin/obsolete.txt", "outdated")])
        write_zip(self.plugin, "sample-plugin", "plugin", marker="new")
        MODULE.prepare(self.args(old))
        mounted = self.out / "plugin/sample-plugin"
        inode = mounted.stat().st_ino
        self.assertEqual((mounted / "marker.txt").read_text(), "old")
        MODULE.promote(self.out)
        self.assertEqual(mounted.stat().st_ino, inode)
        self.assertEqual((mounted / "marker.txt").read_text(), "new")
        self.assertFalse((mounted / "obsolete.txt").exists())
        self.assertFalse((self.out / "candidate").exists())

    def test_wrong_upgrade_plugin_slug_fails_without_output(self):
        old = self.base / "previous.zip"
        write_zip(old, "unrelated-plugin", "plugin")
        with self.assertRaisesRegex(ValueError, "different slugs"):
            MODULE.prepare(self.args(old))
        self.assertFalse(self.out.exists())

    def test_archive_traversal_is_rejected(self):
        write_zip(self.plugin, "sample-plugin", "plugin",
                  extra=[("sample-plugin/../outside.txt", "x")])
        with self.assertRaisesRegex(ValueError, "unsafe archive"):
            MODULE.prepare(self.args())
        self.assertFalse((self.base / "outside.txt").exists())

    def test_archive_symlink_is_rejected(self):
        with zipfile.ZipFile(self.plugin, "w") as z:
            z.writestr("sample-plugin/test-plugin.php", "<?php /* Plugin Name: Test */")
            link = zipfile.ZipInfo("sample-plugin/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(link, "other-target")
        with self.assertRaisesRegex(ValueError, "unsafe archive"):
            MODULE.prepare(self.args())

    def test_two_roots_are_rejected(self):
        write_zip(self.plugin, "sample-plugin", "plugin",
                  extra=[("second-root/evil.php", "<?php")])
        with self.assertRaisesRegex(ValueError, "one top-level"):
            MODULE.prepare(self.args())

    def test_missing_plugin_header_is_rejected(self):
        with zipfile.ZipFile(self.plugin, "w") as z:
            z.writestr("sample-plugin/index.php", "<?php echo 'hi';")
        with self.assertRaisesRegex(ValueError, "missing bootstrap"):
            MODULE.prepare(self.args())

    def test_duplicate_archive_entries_are_rejected(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.plugin, "w") as z:
                z.writestr("sample-plugin/test-plugin.php", "<?php /* Plugin Name: Test */")
                z.writestr("sample-plugin/test-plugin.php", "<?php /* Plugin Name: Test */")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            MODULE.prepare(self.args())


if __name__ == "__main__":
    unittest.main()
