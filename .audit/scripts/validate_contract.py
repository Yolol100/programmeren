#!/usr/bin/env python3
import json
import sys
from pathlib import Path

CONTRACT = Path('.audit/contract.json')
WORKFLOW = Path('.github/workflows/full-plugin-audit.yml')


def fail(message: str) -> None:
    print(f'contract error: {message}', file=sys.stderr)
    raise SystemExit(2)


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
    }
    for key, value in expected.items():
        if harness.get(key) != value:
            fail(f'harness.{key} must be {value!r}')

    required_fields = set((contract.get('request') or {}).get('required_fields') or [])
    expected_fields = {
        'request_id', 'target_repo', 'target_ref', 'target_path', 'run_runtime', 'php_version'
    }
    if required_fields != expected_fields:
        fail(f'request.required_fields drift: expected {sorted(expected_fields)}, got {sorted(required_fields)}')

    security = contract.get('security') or {}
    if security.get('harness_visibility') != 'public':
        fail('current repository contract must declare public harness visibility')
    if security.get('private_target_policy') != 'blocked':
        fail('public harness must block private targets')
    if security.get('target_write_policy') != 'read-only':
        fail('target repository must stay read-only')
    if security.get('request_write_scope') != '.audit/request.json only':
        fail('ChatGPT write scope must stay limited to .audit/request.json')

    try:
        workflow = WORKFLOW.read_text(encoding='utf-8')
    except OSError as exc:
        fail(f'cannot read workflow: {exc}')

    required_workflow_fragments = [
        'name: Full WordPress Plugin Audit',
        'workflow_dispatch:',
        "- '.audit/request.json'",
        'permissions:\n  contents: read',
        'REQUEST_FILE: .audit/request.json',
        '.audit/scripts/check_target_visibility.sh',
    ]
    for fragment in required_workflow_fragments:
        if fragment not in workflow:
            fail(f'workflow contract fragment missing: {fragment!r}')

    print('canonical audit harness contract: OK')


if __name__ == '__main__':
    main()
