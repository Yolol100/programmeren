#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

ROOT = Path('.audit/profiles')
INDEX = ROOT / 'index.json'
ID_RE = re.compile(r'^[a-z0-9][a-z0-9.-]*$')
EXT_RE = re.compile(r'^[A-Za-z0-9_.-]+(?:\s*,\s*[A-Za-z0-9_.-]+)*$|^$')


def fail(message: str) -> None:
    print(f'profile contract error: {message}', file=sys.stderr)
    raise SystemExit(2)


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f'cannot read {path}: {exc}')
    if not isinstance(value, dict):
        fail(f'{path} must contain an object')
    return value


def main() -> None:
    index = load(INDEX)
    if index.get('schema_version') != '1.0':
        fail('index schema_version must be 1.0')
    profiles = index.get('profiles') or {}
    if not isinstance(profiles, dict) or 'base' not in profiles:
        fail('profiles must register base')
    if index.get('default_profile') != 'base':
        fail('default_profile must remain base')

    loaded = {}
    for profile_id, rel in profiles.items():
        if not ID_RE.fullmatch(profile_id):
            fail(f'invalid profile id: {profile_id!r}')
        path = (ROOT / str(rel)).resolve()
        try:
            path.relative_to(ROOT.resolve())
        except ValueError:
            fail(f'profile escapes root: {rel}')
        data = load(path)
        if data.get('id') != profile_id:
            fail(f'profile id mismatch: {rel}')
        if data.get('schema_version') != '1.0':
            fail(f'{rel} schema_version must be 1.0')
        if not isinstance(data.get('capabilities') or [], list):
            fail(f'{rel} capabilities must be a list')
        runtime = data.get('runtime') or {}
        if not isinstance(runtime, dict):
            fail(f'{rel} runtime must be an object')
        extensions = str(runtime.get('php_extensions') or '')
        if not EXT_RE.fullmatch(extensions):
            fail(f'{rel} php_extensions is invalid')
        script = str(runtime.get('script') or '')
        if script:
            if not script.startswith('.audit/scripts/') or not Path(script).is_file():
                fail(f'{rel} runtime script is invalid: {script}')
        loaded[profile_id] = data

    visiting = set()
    visited = set()

    def visit(profile_id: str) -> None:
        if profile_id in visited:
            return
        if profile_id in visiting:
            fail(f'inheritance cycle at {profile_id}')
        visiting.add(profile_id)
        for parent in loaded[profile_id].get('extends') or []:
            if parent not in loaded:
                fail(f'{profile_id} extends unknown profile {parent}')
            visit(parent)
        visiting.remove(profile_id)
        visited.add(profile_id)

    for profile_id in loaded:
        visit(profile_id)

    seen_repositories = {}
    for binding in index.get('bindings') or []:
        if not isinstance(binding, dict):
            fail('binding must be an object')
        profile_id = binding.get('profile')
        if profile_id not in loaded:
            fail(f'binding references unknown profile {profile_id!r}')
        if profile_id == 'base':
            fail('base must be fallback-only and may not have an explicit binding')
        for repo in binding.get('repositories') or []:
            key = str(repo).lower()
            other = seen_repositories.get(key)
            if other and other != profile_id:
                fail(f'repository {repo} is bound to both {other} and {profile_id}')
            seen_repositories[key] = profile_id
        identity = binding.get('plugin_identity') or {}
        if identity:
            required = {'main_file', 'plugin_name', 'text_domain'}
            missing = sorted(required - set(identity))
            if missing:
                fail(f'{profile_id} plugin_identity missing {missing}')

    print(f'plugin-aware audit profiles: OK ({len(loaded)} profiles, {len(index.get("bindings") or [])} bindings)')


if __name__ == '__main__':
    main()
