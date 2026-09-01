# Programmeren repository instructions

## Scope
- This repository is a WordPress/plugin audit harness and controlled evidence adapter for `wordpressqualityarchitect`; it is not the content or release owner.
- `webactueel-workflow` remains the controller for cross-skill routing, source selection, handoffs and total workflow closure.
- Prefer native Codex repository/toolchain execution when the exact local repository runtime can produce the same evidence class. Use this harness when standardized cross-repository CI evidence, isolated remote auditing or persisted artifacts are needed.

## Before changing files
- Read `README.md`, `.audit/contract.json`, `.audit/profiles/index.json` and `.github/workflows/full-plugin-audit.yml` before changing audit behavior.
- Keep `main` generic. Concrete `.audit/request.json` state belongs only on temporary `runtime/**` branches or an explicit workflow-dispatch input.
- Preserve immutable target commit capture, base-profile fail-closed behavior, public/private evidence boundaries and pinned audit tooling.
- Never commit target credentials, private plugin source copied from restricted repositories, secrets or run-specific artifacts.

## Validation
Use the repository entrypoints:

```bash
bash script/validate
bash script/audit
```

Use `bash script/package` only when a package artifact is actually part of the task. For contract/profile/workflow changes, also run the corresponding `.audit/scripts/` validators and routing tests referenced by the workflow.

## Evidence boundaries
- Scanner findings are candidate evidence until `wordpressqualityarchitect` validates them.
- A CycloneDX SBOM is inventory/provenance evidence, not proof of dependency safety, licensing or exploitability.
- A green audit proves only executed static/controlled-runtime layers; it is not staging, production, full browser/device or human accessibility proof.
- Do not merge, publish or deploy solely because the harness is green.
