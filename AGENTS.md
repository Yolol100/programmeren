# Programmeren — agentcontract

## Rol
- Generieke WordPress/plugin-audit-harness voor `wordpressqualityarchitect`; `webactueel-workflow` blijft controller. Geen domein-, productie- of release-eigenaar.
- Kies eerst native Codex voor gelijkwaardig lokaal bewijs; gebruik deze repo bij gestandaardiseerde remote audits, cross-repo CI of persistente evidence.
- Lees bij wijzigingen `README.md`, `.audit/contract.json`, `.audit/profiles/index.json` en de relevante `.github/workflows/full-plugin-audit.yml`.

## Grenzen
- `main` bevat alleen generieke base-profielen, tests en tooling. Concrete `.audit/request.json` uitsluitend op tijdelijke `runtime/**`-branches of expliciete dispatch. Geen klant-, plugin-, URL- of runspecifieke state, secrets of private code in de default branch.
- Scope acties als `read_only`, `safe_write` (klein, omkeerbaar, preflight/readback) of `high_risk_write` (uitdrukkelijke toestemming, rollback en sterkere tests). Een groene CI verleent nooit vanzelf extra schrijfrechten of toestemming voor productie.
- Houd runtimebewijs, targetcommit, toolpinning, public/private-grenzen, contracts en vaste basischecks intact. Nieuwe externe patronen of Library/YouTube-inhoud zijn hooguit aanvullend; actuele primaire bron en owner beslissen.

## Verificatie
- Gebruik `bash script/validate` en bij een echte audit `bash script/audit`; `bash script/package` alleen voor gevraagde packages. Test bij contractwijzigingen ook de geraakte `.audit/scripts/`-validators.
- Scanner, SBOM en CI bewijzen uitsluitend de uitgevoerde checks: geen productieveiligheid, licentie-, staging-, browser- of WCAG-garantie. Rapporteer ontbrekend bewijs; geen merge, publicatie of deploy zonder aparte acceptatie.
