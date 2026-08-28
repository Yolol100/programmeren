#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

CONTRACT = Path('.audit/contract.json')
WORKFLOW = Path('.github/workflows/full-plugin-audit.yml')
DEFAULT_REQUEST = Path('.audit/request.json')


def fail(message: str) -> None:
    print(f'contract error: {message}', file=sys.stderr)
    raise SystemExit(2)


def current_ref_name() -> str:
    for key in ('AUDIT_CONTRACT_REF_NAME', 'GITHUB_REF_NAME'):
        value = os.environ.get(key, '').strip()
        if value:
            return value
    try:
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ''
    return result.stdout.strip() if result.returncode == 0 else ''


def main() -> None:
    try:
        contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f'cannot read canonical contract: {exc}')

    harness = contract.get('harness') or {}
    expected = {
        'repository': 'Yolol100/programmeren',
        'default_branch': 'main',
        'workflow_name': 'Full WordPress Plugin Audit',
        'workflow_file': '.github/workflows/full-plugin-audit.yml',
        'request_file': '.audit/request.json',
        'request_branch_pattern': 'runtime/**',
    }
    for key, value in expected.items():
        if harness.get(key) != value:
            fail(f'harness.{key} must be {value!r}')

    ref_name = current_ref_name()
    if DEFAULT_REQUEST.exists() and not ref_name.startswith('runtime/'):
        fail(
            '.audit/request.json is allowed only on runtime/** branches; '
            f'current ref is {ref_name or "unknown"!r}'
        )

    required_fields = set((contract.get('request') or {}).get('required_fields') or [])
    expected_fields = {
        'request_id', 'target_repo', 'target_ref', 'target_path', 'run_runtime', 'php_version'
    }
    if required_fields != expected_fields:
        fail(f'request.required_fields drift: expected {sorted(expected_fields)}, got {sorted(required_fields)}')

    routing = contract.get('profile_routing') or {}
    expected_routing = {
        'registry': '.audit/profiles/index.json',
        'resolver': '.audit/scripts/resolve_profile.py',
        'validator': '.audit/scripts/validate_profiles.py',
        'default_profile': 'base',
        'unknown_target_policy': 'base-only',
    }
    for key, value in expected_routing.items():
        if routing.get(key) != value:
            fail(f'profile_routing.{key} must be {value!r}')

    security = contract.get('security') or {}
    if security.get('harness_visibility') != 'public':
        fail('current repository contract must declare public harness visibility')
    if security.get('private_target_policy') != 'blocked':
        fail('public harness must block private targets')
    if security.get('target_write_policy') != 'read-only':
        fail('target repository must stay read-only')
    if security.get('request_write_scope') != 'runtime/** branch .audit/request.json only':
        fail('file-backed request writes must stay isolated to runtime/** branches')
    if security.get('default_branch_request_state') != 'forbidden':
        fail('default-branch request state must be forbidden')

    try:
        workflow = WORKFLOW.read_text(encoding='utf-8')
    except OSError as exc:
        fail(f'cannot read workflow: {exc}')

    required_workflow_fragments = [
        'name: Full WordPress Plugin Audit',
        'workflow_dispatch:',
        "- 'runtime/**'",
        "- '.audit/request.json'",
        'permissions:\n  contents: read',
        'REF_NAME: ${{ github.ref_name }}',
        'REQUEST_FILE: .audit/request.json',
        '.audit/scripts/check_target_visibility.sh',
        '.audit/scripts/validate_profiles.py',
        '.audit/scripts/resolve_profile.py',
        'profile-runtime:',
        "needs.audit.outputs.specialized_runtime == 'true'",
        'image: ${{ matrix.mysql_image }}',
        'image: ${{ matrix.redis_image }}',
    ]
    for fragment in required_workflow_fragments:
        if fragment not in workflow:
            fail(f'workflow contract fragment missing: {fragment!r}')
    if "branches:\n      - main\n    paths:\n      - '.audit/request.json'" in workflow:
        fail('concrete request-file pushes may not target main')

    print('canonical audit harness contract: OK')


if __name__ == '__main__':
    main()
