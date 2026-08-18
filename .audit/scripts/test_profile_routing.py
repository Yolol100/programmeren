#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESOLVER = ROOT / '.audit/scripts/resolve_profile.py'


def run_case(target_repo: str, plugin_files: dict) -> None:
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
        assert outputs['profile_id'] == 'base', outputs
        assert outputs['profile_match'] == 'default', outputs
        assert outputs['specialized_runtime'] == 'false', outputs
        resolution = json.loads((results / 'profile-resolution.json').read_text(encoding='utf-8'))
        assert resolution['profile_id'] == 'base', resolution
        assert resolution['matched_by'] == 'default', resolution
        assert resolution['runtime']['specialized'] is False, resolution


def main() -> None:
    generic = {
        'example.php': "<?php\n/**\n * Plugin Name: Example Plugin\n * Text Domain: example-plugin\n */\n",
    }
    cache_like = {
        'cache-plugin.php': "<?php\n/**\n * Plugin Name: Cache Plugin\n * Text Domain: cache-plugin\n */\n",
        'advanced-cache.php': '<?php\n',
        'dropins/': '',
        'includes/': '',
    }
    run_case('Acme/example-plugin', generic)
    run_case('Acme/cache-plugin', cache_like)
    print('profile routing regression tests: OK')


if __name__ == '__main__':
    main()
