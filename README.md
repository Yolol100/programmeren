# Programmeren - WordPress Plugin Audit Harness

Centrale auditomgeving voor WordPress-plugins. De repository levert gecontroleerd bewijs; `wordpressqualityarchitect` blijft eigenaar van de inhoudelijke beoordeling.

## Kern

De generieke `base`-audit voert waar toepasbaar uit:

- PHP syntaxcontrole;
- WordPress Coding Standards;
- PHPCompatibilityWP en PHPStan voor WordPress;
- Composer- en npm-audits wanneer lockfiles aanwezig zijn;
- Gitleaks, Semgrep CE en Trivy;
- actionlint en zizmor voor GitHub Actions;
- WordPress Plugin Check;
- een gecontroleerde WordPress-runtime via `wp-env` wanneer runtime is aangezet;
- immutable target-provenance, logs en artifacts.

De centrale tooling is gepind en werkt zonder apart account, API-key of MCP-server.

## Profielrouting

`.audit/profiles/index.json` is de profielregistry. Op dit moment is alleen het generieke `base`-profiel actief en zijn er geen product-specifieke bindings. Daardoor valt iedere plugin veilig terug op dezelfde basiscontrole.

De resolver en validator blijven aanwezig zodat later alleen bij een expliciete, geteste noodzaak een gespecialiseerd profiel kan worden toegevoegd. Onbekende plugins mogen nooit automatisch gespecialiseerde services of runtimecode activeren.

```text
.audit/profiles/
  index.json
  base.json
```

## Starten

### Handmatig in GitHub

Gebruik **Actions -> Full WordPress Plugin Audit -> Run workflow** en vul minimaal `target_repo` in als `owner/repository`.

### Via ChatGPT

Voor een expliciete plugin-audit schrijft ChatGPT via de gekoppelde GitHub-app een generiek verzoek naar `.audit/request.json`. Alleen een wijziging van dat bestand op `main` start deze automatische route.

Voor iedere echte audit hoort het verzoek een unieke `request_id` te krijgen. Het ingecheckte baselineverzoek wijst naar de veilige interne fixture en bevat geen klant- of productspecifieke targetinformatie.

Voorbeeld:

```json
{
  "request_id": "2026-08-18-example",
  "target_repo": "owner/plugin-repository",
  "target_ref": "main",
  "target_path": ".",
  "run_runtime": true,
  "php_version": "8.3"
}
```

De machineleesbare route- en veiligheidsafspraken staan in `.audit/contract.json`.

## Veiligheidsgrenzen

- Het doelproject wordt read-only behandeld.
- De workflow heeft standaard alleen `contents: read`.
- Private targets worden geweigerd zolang deze harness publiek is.
- Credentials horen niet in artifacts.
- Willekeurige Composer-scripts of plugins uit het doelproject worden niet door de statische audit geïnstalleerd.
- Runtime draait alleen wanneer `run_runtime=true` is gekozen.
- Scannerhits zijn kandidaat-findings; pas specialistische validatie maakt er een bevestigde bevinding van.

## Bewijsgrens

Een groene run bewijst alleen de werkelijk uitgevoerde statische en controlled-runtime checks. Het is geen bewijs voor staging, productie, een volledige browser/device-matrix of menselijke toegankelijkheidstests.

## Self-test en contract

`.audit/fixtures/programmeren-audit-fixture` is de minimale veilige fixture. `Toolkit Contract` valideert de audittooling, profielrouting en immutable target-provenance. De generieke request op `main` kan de fixture gebruiken om de volledige triggerroute zonder productspecifieke inhoud te controleren.
