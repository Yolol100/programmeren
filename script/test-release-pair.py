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
        self.assertEqual(config["core"], MODULE.WORDPRESS_CORE_REF)
        self.assertEqual(config["mariadbVersion"], MODULE.MARIADB_VERSION)
        self.assertEqual(receipt["wordpress_core_ref"], MODULE.WORDPRESS_CORE_REF)
        self.assertEqual(receipt["mariadb_version"], MODULE.MARIADB_VERSION)
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

    def test_explicit_top_level_directories_are_accepted(self):
        for archive, root in ((self.theme, "sample-theme/"),
                              (self.plugin, "sample-plugin/")):
            with zipfile.ZipFile(archive, "a") as z:
                z.writestr(root, "")
        MODULE.prepare(self.args())
        self.assertTrue((self.out / "theme/sample-theme/style.css").is_file())
        self.assertTrue((self.out / "plugin/sample-plugin/test-plugin.php").is_file())

    def test_identical_previous_plugin_cannot_claim_upgrade(self):
        with self.assertRaisesRegex(ValueError, "identical"):
            MODULE.prepare(self.args(self.plugin))
        self.assertFalse(self.out.exists())

    def test_workflow_uses_reachable_pr_sha_and_pins_plugin_check(self):
        workflow = (MODULE_PATH.parent.parent / ".github" / "workflows" /
                    "wordpress-release-pair.yml").read_text()
        self.assertIn("job.workflow_repository", workflow)
        self.assertIn("job.workflow_sha", workflow)
        self.assertNotIn("github.head_ref", workflow)
        self.assertRegex(workflow, r"wp plugin install plugin-check --version=\d+\.\d+\.\d+ --activate")

    def test_workflow_records_unique_per_invocation_artifacts(self):
        workflow = (MODULE_PATH.parent.parent / ".github" / "workflows" /
                    "wordpress-release-pair.yml").read_text()
        self.assertIn("evidence_id:", workflow)
        self.assertIn("${{ github.run_attempt }}-${{ inputs.evidence_id }}", workflow)
        self.assertIn("EVIDENCE_ID: ${{ inputs.evidence_id }}", workflow)

    def test_upgrade_plugin_check_uses_update_mode(self):
        workflow = (MODULE_PATH.parent.parent / ".github" / "workflows" /
                    "wordpress-release-pair.yml").read_text()
        self.assertIn("check_mode='update'", workflow)
        self.assertIn('--mode="$check_mode"', workflow)

    def test_theme_is_rechecked_after_plugin_activations(self):
        runtime = MODULE_PATH.with_name("release-pair-runtime.sh").read_text()
        self.assertIn('wp-env run cli wp theme is-active "$theme_slug"', runtime)
        self.assertIn('theme_active=passed', runtime)

    def test_sentinel_content_and_status_are_preserved(self):
        runtime = MODULE_PATH.with_name("release-pair-runtime.sh").read_text()
        self.assertIn('$post->post_status !== "draft"', runtime)
        self.assertIn('$post->post_content !== "This is isolated test content."', runtime)

    def test_optional_disabled_checks_have_not_run_evidence(self):
        workflow = (MODULE_PATH.parent.parent / ".github" / "workflows" /
                    "wordpress-release-pair.yml").read_text()
        self.assertIn('plugin-check-status.txt', workflow)
        self.assertIn('lighthouse-status.txt', workflow)
        self.assertIn('NOT_RUN_DISABLED_BY_INPUT', workflow)

    def test_validation_leaves_no_python_bytecode_cache(self):
        validate = MODULE_PATH.with_name("validate").read_text()
        self.assertIn("PYTHONDONTWRITEBYTECODE=1 python3 script/test-release-pair.py", validate)
        self.assertNotIn("python3 -m py_compile script/release-pair-prepare.py", validate)

    def test_optional_check_status_includes_upstream_failure(self):
        workflow = (MODULE_PATH.parent.parent / ".github" / "workflows" /
                    "wordpress-release-pair.yml").read_text()
        self.assertIn("steps.plugin_check.outcome", workflow)
        self.assertIn("steps.lighthouse.outcome", workflow)
        self.assertIn("NOT_RUN_UPSTREAM_FAILURE", workflow)
        self.assertIn("record_status", workflow)

    def test_frontend_smoke_refuses_redirects(self):
        runtime = MODULE_PATH.with_name("release-pair-runtime.sh").read_text()
        self.assertIn("--max-redirs 0", runtime)

    def test_metadata_only_zip_change_is_not_an_upgrade(self):
        old = self.base / "previous.zip"
        old.write_bytes(self.plugin.read_bytes())
        with zipfile.ZipFile(old, "a") as z:
            z.comment = b"different ZIP metadata; identical extracted plugin"
        self.assertNotEqual(old.read_bytes(), self.plugin.read_bytes())
        with self.assertRaisesRegex(ValueError, "contents are identical"):
            MODULE.prepare(self.args(old))
        self.assertFalse(self.out.exists())

    def test_verification_isolated_and_repeated_after_http(self):
        runtime = MODULE_PATH.with_name("release-pair-runtime.sh").read_text()
        self.assertIn('wp --skip-plugins --skip-themes plugin is-active', runtime)
        self.assertIn('wp --skip-plugins --skip-themes theme is-active', runtime)
        self.assertIn('wp --skip-plugins --skip-themes eval', runtime)
        self.assertEqual(runtime.count("\nverify_release_state\n"), 2)
        self.assertLess(runtime.index('curl --fail'), runtime.rindex('verify_release_state'))

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
