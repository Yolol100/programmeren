# Programmeren - WordPress Plugin Audit Harness

Centrale auditomgeving voor WordPress-plugins. De repository levert gecontroleerd bewijs; `wordpressqualityarchitect` blijft eigenaar van de inhoudelijke beoordeling.

## Kern

De generieke `base`-audit voert waar toepasbaar uit:

- PHP syntaxcontrole;
- WordPress Coding Standards;
- PHPCompatibilityWP en PHPStan voor WordPress;
- Composer- en npm-audits wanneer lockfiles aanwezig zijn;
- Gitleaks, Semgrep CE en Trivy;
- een gevalideerde CycloneDX-SBOM met SHA-256-fingerprint als dependency/provenance-evidence;
- actionlint en zizmor voor GitHub Actions;
- WordPress Plugin Check;
- een gecontroleerde WordPress-runtime via `wp-env` wanneer runtime is aangezet;
- immutable target-provenance, logs en artifacts.

De centrale tooling is gepind en werkt zonder apart account, API-key of MCP-server.

## Onderhoud en bijdragen

De repository gebruikt een kleine set vaste conventies:

- Dependabot controleert maandelijks alleen GitHub Actions. De gepinde Composer-audittooling blijft bewust buiten automatische updates omdat wijzigingen samen met de vaste dependency-hash en regressietests moeten worden gevalideerd.
- `Dependency Review` controleert pull requests op nieuw geintroduceerde dependencykwetsbaarheden en blokkeert vanaf `high` severity.
- Pull requests en issues vragen expliciet om scope, bewijs, verificatie en waar relevant rollbackinformatie.
- Eenvoudige entrypoints verbergen interne paden zonder een tweede auditimplementatie te maken.

Gebruik lokaal of in een geschikte repositoryruntime:

```bash
bash script/validate
bash script/audit
bash script/package
```

`script/audit` is een dunne wrapper rond de bestaande statische audit en verwacht dezelfde gevalideerde environment, tooling en profile-resolution evidence als de workflow. Voor normale audits blijft **Full WordPress Plugin Audit** de voorkeursroute.

`script/package` maakt een Git-archive van de huidige commit en schrijft daarnaast een SHA-256-checksum. Standaard komt dit in `dist/`; zet `OUTPUT_DIR` wanneer een andere tijdelijke uitvoermap nodig is.

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

### Via ChatGPT / GitHub-connector

Concrete auditrequest-state hoort niet op `main`. Voor een connector-gestuurde audit wordt vanaf de actuele `main` een unieke tijdelijke `runtime/**`-branch gemaakt. Alleen op die branch mag `.audit/request.json` met de concrete requestvelden worden geschreven. De workflow luistert op dat pad uitsluitend binnen `runtime/**`.

Na readback van request + commit kan de run aan die request worden gekoppeld. Zodra het vereiste runbewijs veilig is vastgelegd, kan de tijdelijke runtimebranch worden verwijderd. De default branch blijft daardoor generieke capability zonder klant-, target- of runstate.

Voorbeeld van de tijdelijke requestinhoud:

```json
{
  "request_id": "run-unique-id",
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
- Concrete auditrequest-state is verboden op `main`; file-backed requests zijn alleen toegestaan op een tijdelijke `runtime/**`-branch.
- Credentials horen niet in artifacts.
- Willekeurige Composer-scripts of plugins uit het doelproject worden niet door de statische audit geïnstalleerd.
- Runtime draait alleen wanneer `run_runtime=true` is gekozen.
- Scannerhits zijn kandidaat-findings; pas specialistische validatie maakt er een bevestigde bevinding van.
- De CycloneDX-SBOM is inventaris/provenance-evidence en bewijst op zichzelf geen dependencyveiligheid, licentiecompliance of exploitability.

## Bewijsgrens

Een groene run bewijst alleen de werkelijk uitgevoerde statische en controlled-runtime checks. Het is geen bewijs voor staging, productie, een volledige browser/device-matrix of menselijke toegankelijkheidstests.

## Self-test en contract

`.audit/fixtures/programmeren-audit-fixture` is de minimale veilige fixture. `Toolkit Contract` valideert de audittooling, profielrouting, immutable target-provenance, verplichte SBOM-evidence, onderhoudsconventies en de regel dat concrete request-state niet op de default branch staat.
