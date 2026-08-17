#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESOLVER = ROOT / '.audit/scripts/resolve_profile.py'
PROFILE_RUNTIME = ROOT / '.audit/scripts/integration_runtime_probe.sh'


def run_case(target_repo: str, plugin_files: dict, expected_profile: str, expected_match: str) -> None:
    with tempfile.TemporaryDirectory(prefix='programmeren-profile-test-') as temp:
        temp_path = Path(temp)
        plugin_dir = temp_path / 'plugin'
        results = temp_path / 'results'
        plugin_dir.mkdir()
        for rel, content in plugin_files.items():
            path = plugin_dir / rel
            if rel.endswith('/'):
                path.mkdir(parents=True, exist_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        env = os.environ.copy()
        env.update({
            'TARGET_REPO': target_repo,
            'PLUGIN_DIR': str(plugin_dir),
            'RESULTS_DIR': str(results),
        })
        proc = subprocess.run(
            [sys.executable, str(RESOLVER)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(f'resolver failed for {target_repo}: {proc.stderr}')
        outputs = {}
        for line in proc.stdout.splitlines():
            key, value = line.split('=', 1)
            outputs[key] = value
        assert outputs['profile_id'] == expected_profile, outputs
        assert outputs['profile_match'] == expected_match, outputs
        resolution = json.loads((results / 'profile-resolution.json').read_text(encoding='utf-8'))
        assert resolution['profile_id'] == expected_profile


def assert_ultracache_state_changes_use_admin_post() -> None:
    probe = PROFILE_RUNTIME.read_text(encoding='utf-8')
    for check_name in (
        'ucp-redis-dropin-install',
        'ucp-redis-dropin-remove',
        'ucp-apcu-dropin-install',
        'ucp-apcu-dropin-remove',
    ):
        matches = [
            line for line in probe.splitlines()
            if f'run_check "{check_name}"' in line
        ]
        assert len(matches) == 1, (check_name, matches)
        line = matches[0]
        assert 'wp_set_current_user(1)' in line, line
        assert '$_SERVER["REQUEST_METHOD"]="POST"' in line, line
        assert 'wp_create_nonce(' in line, line


def main() -> None:
    generic = {
        'example.php': "<?php\n/**\n * Plugin Name: Example Plugin\n * Text Domain: example-plugin\n */\n",
    }
    ultracache = {
        'ultracache-pro.php': "<?php\n/**\n * Plugin Name: UltraCache Pro\n * Text Domain: ultracache-pro\n */\n",
        'advanced-cache.php': '<?php\n',
        'dropins/': '',
        'includes/': '',
    }
    run_case('Acme/example-plugin', generic, 'base', 'default')
    run_case('ForkOwner/cache-fork', ultracache, 'ultracache-pro', 'plugin_identity')
    run_case('Yolol100/Ultracache-pro', ultracache, 'ultracache-pro', 'repository')
    assert_ultracache_state_changes_use_admin_post()
    print('profile routing regression tests: OK')


if __name__ == '__main__':
    main()
