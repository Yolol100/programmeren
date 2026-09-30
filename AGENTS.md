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

## Externe kenniscontext
- De gedeelde Library-corpus `Webactueel Kennisbronnen/YouTube/YouTube_Kennisbron_Master.zip` mag door `webactueel-workflow` en `wordpressqualityarchitect` worden gebruikt voor discovery, voorbeelden en hypothesevorming.
- Kopieer transcriptrecords of corpusshards nooit naar deze repository of naar `main`. De corpus is geen projectwaarheid en geen auditartifact.
- Een videobron bewijst geen actuele API-, security-, release- of runtimeclaim. Valideer materiele claims tegen de actieve Project Plugin/Programmeren-bron, actuele primaire makerdocumentatie en de vereiste uitvoeringslaag.
- Houd auditbewijs strikt bij de werkelijk uitgevoerde source/controlled-runtime checks; externe kenniscontext mag de status van een auditrun niet groen maken.

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

## Agent-capability- en impactbeleid

Voordat een agent repository- of externe state wijzigt:

- Classificeer de bedoelde actie als `read_only`, `safe_write` of `high_risk_write`.
- `read_only` mag inspecteren, zoeken, diffen, linten en testen zonder externe state te muteren.
- `safe_write` moet begrensd en omkeerbaar zijn, met target-preflight, stale-state/idempotency-bescherming waar relevant, exacte readback en rollback wanneer het target dit ondersteunt.
- `high_risk_write` omvat destructieve, productie-, deploy-, publicatie-, permission-, securitygevoelige of breed gescopeerde mutaties. Houd die achter expliciete owner/approval en sterkere verificatie.
- Toolbeschikbaarheid, een agentverzoek of groene CI verleent nooit vanzelf extra schrijfrechten.

Bouw vóór niet-triviale bronwijzigingen een begrensde impactcontext uit gewijzigde paden, directe imports/afhankelijkheden, relevante contracten/workflows en de tests die het gedrag bewijzen. Een gegenereerde graph/index is alleen commit-gebonden evidence/cache: geen projectwaarheid, duurzaam geheugen of tweede controller.

GitHub Trending en externe repositories zijn alleen discovery-signalen. Distilleer patronen en verifieer die daarna tegen het ownercontract, actuele primaire/officiële documentatie en lokale regressie-evidence. Kopieer geen code, prompts, assets of configuratie zonder compatibele gebruiksrechten en een expliciete repositoryreden.

