#!/usr/bin/env python3
import hashlib
import json
import os
import re
import sys
from pathlib import Path

INDEX = Path('.audit/profiles/index.json')
PROFILE_ROOT = INDEX.parent
COMMENT_PREFIX_RE = re.compile(r'^(?:/\*+|\*+|//+|#+)\s*')


def fail(message: str) -> None:
    print(f'profile error: {message}', file=sys.stderr)
    raise SystemExit(2)


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f'cannot read {path}: {exc}')
    if not isinstance(data, dict):
        fail(f'{path} must contain a JSON object')
    return data


def headers_for(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding='utf-8', errors='replace')[:16384]
    except OSError:
        return {}
    headers = {}
    for raw_line in text.splitlines():
        line = COMMENT_PREFIX_RE.sub('', raw_line.strip())
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        key = key.strip().lower()
        if key in {'plugin name', 'text domain', 'github plugin uri'}:
            headers[key] = value.strip().removesuffix('*/').strip()
    return headers


def merge_runtime(base: dict, overlay: dict) -> dict:
    merged = dict(base)
    for key, value in overlay.items():
        if value not in (None, ''):
            merged[key] = value
    return merged


def main() -> None:
    target_repo = os.environ.get('TARGET_REPO', '').strip()
    plugin_dir = Path(os.environ.get('PLUGIN_DIR', 'target-repo')).resolve()
    if not target_repo or '/' not in target_repo:
        fail('TARGET_REPO must be owner/repository')
    if not plugin_dir.is_dir():
        fail(f'PLUGIN_DIR does not exist: {plugin_dir}')

    index = load_json(INDEX)
    profile_files = index.get('profiles') or {}
    if not isinstance(profile_files, dict) or not profile_files:
        fail('profiles index is empty')
    default_profile = str(index.get('default_profile') or '').strip()
    if default_profile not in profile_files:
        fail('default_profile is not registered')

    loaded = {}

    def get_profile(profile_id: str) -> dict:
        if profile_id in loaded:
            return loaded[profile_id]
        rel = profile_files.get(profile_id)
        if not isinstance(rel, str) or not rel:
            fail(f'profile {profile_id!r} has no registered file')
        path = (PROFILE_ROOT / rel).resolve()
        try:
            path.relative_to(PROFILE_ROOT.resolve())
        except ValueError:
            fail(f'profile file escapes profile root: {rel}')
        data = load_json(path)
        if data.get('id') != profile_id:
            fail(f'profile id mismatch in {rel}')
        data['_file'] = str(Path('.audit/profiles') / rel)
        loaded[profile_id] = data
        return data

    candidates = []
    for binding in index.get('bindings') or []:
        if not isinstance(binding, dict):
            fail('every binding must be an object')
        profile_id = str(binding.get('profile') or '')
        get_profile(profile_id)

        repositories = [str(v).lower() for v in (binding.get('repositories') or [])]
        repo_match = target_repo.lower() in repositories

        identity = binding.get('plugin_identity') or {}
        identity_match = False
        if identity:
            main_file = str(identity.get('main_file') or '')
            main_path = plugin_dir / main_file
            headers = headers_for(main_path)
            required_files = [str(v) for v in (identity.get('required_files') or [])]
            files_match = all((plugin_dir / rel).exists() for rel in required_files)
            name_match = headers.get('plugin name', '') == str(identity.get('plugin_name') or '')
            domain_match = headers.get('text domain', '') == str(identity.get('text_domain') or '')
            identity_match = bool(main_file and main_path.is_file() and files_match and name_match and domain_match)

        if repo_match or identity_match:
            candidates.append({
                'profile': profile_id,
                'match': 'repository' if repo_match else 'plugin_identity',
            })

    unique = {item['profile'] for item in candidates}
    if len(unique) > 1:
        fail(f'conflicting profile bindings matched: {sorted(unique)}')

    selected = next(iter(unique), default_profile)
    matched_by = candidates[0]['match'] if candidates else 'default'

    chain = []
    visiting = set()

    def visit(profile_id: str) -> None:
        if profile_id in chain:
            return
        if profile_id in visiting:
            fail(f'profile inheritance cycle at {profile_id}')
        visiting.add(profile_id)
        profile = get_profile(profile_id)
        for parent in profile.get('extends') or []:
            visit(str(parent))
        visiting.remove(profile_id)
        chain.append(profile_id)

    visit(selected)

    capabilities = []
    runtime = {
        'specialized': False,
        'script': '',
        'php_extensions': '',
        'node_version': '',
        'mysql_image': '',
        'redis_image': '',
        'wordpress_plugins': [],
    }
    profile_version = ''
    profile_file = ''
    for profile_id in chain:
        profile = get_profile(profile_id)
        for capability in profile.get('capabilities') or []:
            capability = str(capability)
            if capability not in capabilities:
                capabilities.append(capability)
        runtime = merge_runtime(runtime, profile.get('runtime') or {})
        if profile_id == selected:
            profile_version = str(profile.get('version') or '')
            profile_file = profile['_file']

    script = str(runtime.get('script') or '')
    if runtime.get('specialized'):
        if not script.startswith('.audit/scripts/') or not Path(script).is_file():
            fail(f'specialized profile {selected} has invalid runtime script: {script!r}')

    resolution = {
        'schema_version': '1.0',
        'target_repo': target_repo,
        'profile_id': selected,
        'profile_version': profile_version,
        'profile_file': profile_file,
        'matched_by': matched_by,
        'profile_chain': chain,
        'capabilities': capabilities,
        'runtime': runtime,
    }
    canonical = json.dumps(resolution, sort_keys=True, separators=(',', ':')).encode('utf-8')
    resolution['fingerprint_sha256'] = hashlib.sha256(canonical).hexdigest()

    results = Path(os.environ.get('RESULTS_DIR', 'audit-results'))
    results.mkdir(parents=True, exist_ok=True)
    (results / 'profile-resolution.json').write_text(
        json.dumps(resolution, indent=2, sort_keys=True) + '\n', encoding='utf-8'
    )

    runtime_matrix = {
        'include': [{
            'profile_id': selected,
            'runtime_script': script,
            'php_extensions': str(runtime.get('php_extensions') or ''),
            'node_version': str(runtime.get('node_version') or ''),
            'mysql_image': str(runtime.get('mysql_image') or ''),
            'redis_image': str(runtime.get('redis_image') or ''),
        }]
    }
    outputs = {
        'profile_id': selected,
        'profile_version': profile_version,
        'profile_file': profile_file,
        'profile_match': matched_by,
        'profile_fingerprint': resolution['fingerprint_sha256'],
        'capabilities': ','.join(capabilities),
        'specialized_runtime': 'true' if runtime.get('specialized') else 'false',
        'runtime_matrix': json.dumps(runtime_matrix, separators=(',', ':')),
    }
    for key, value in outputs.items():
        print(f'{key}={value}')


if __name__ == '__main__':
    main()
