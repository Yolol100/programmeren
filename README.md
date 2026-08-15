# Programmeren – WordPress Plugin Audit Harness

Centrale, op aanvraag gestarte auditomgeving voor WordPress-plugins.

## Doel

Eén GitHub Actions-run gebruikt één `ubuntu-latest` job en verzamelt meerdere onafhankelijke bewijslagen zonder automatisch bij iedere normale push of pull request te draaien.

De audit bevat waar toepasbaar:

- PHP syntaxcontrole;
- WordPress Coding Standards (WPCS/PHPCS);
- PHPCompatibilityWP;
- PHPStan met WordPress-extensie;
- Composer validate/audit;
- npm audit wanneer een lockfile aanwezig is;
- WordPress Plugin Check;
- Gitleaks secret scan;
- Trivy vulnerability/misconfiguration scan;
- actionlint + zizmor wanneer het doelproject GitHub Actions bevat;
- optionele gecontroleerde WordPress-runtime via `wp-env`;
- source-snapshot ZIP + SHA-256;
- auditlogs en rapporten als GitHub Actions artifact.

## Starten

### Handmatig in GitHub

Ga naar **Actions → Full WordPress Plugin Audit → Run workflow** en vul minimaal `target_repo` in als `owner/repository`.

### Via ChatGPT

ChatGPT kan `.audit/request.json` wijzigen. Alleen een wijziging van dat bestand op `main` triggert de audit automatisch. Normale wijzigingen, pushes en pull requests starten deze workflow niet.

Voorbeeld:

```json
{
  "request_id": "2026-08-15-example",
  "target_repo": "owner/plugin-repository",
  "target_ref": "main",
  "target_path": ".",
  "run_runtime": true,
  "php_version": "8.3"
}
```

## Publiek versus privé

Deze harness-repository is momenteel **public**. Daarom weigert de workflow fail-closed om een **private** doelrepository te auditen: logs en artifacts zouden anders private code of findings kunnen lekken.

Wil je later private plugins auditen, maak deze harness eerst private en voeg daarna zo nodig een read-only repositorytoken toe als Actions secret `PLUGIN_REPO_TOKEN`.

## Bewijsgrens

Een groene run bewijst alleen de uitgevoerde statische en controlled-runtime checks. Het is geen vervanging voor echte staging, productie-observatie, browser/device-matrix, betaalproviders of menselijke toegankelijkheidstests.

## Veiligheid

- De workflow heeft standaard alleen `contents: read`.
- Credentials worden niet in artifacts opgenomen.
- Het doelproject wordt niet gewijzigd of teruggeschreven.
- Projectafhankelijkheden worden voor statische/dependencychecks niet met eigen Composer-scripts/plugins uitgevoerd.
- Runtime-uitvoering gebeurt alleen wanneer `run_runtime=true` is gekozen.
- Scannerhits zijn kandidaat-findings; `wordpressqualityarchitect` bepaalt pas na bewijs of iets een bevestigde bug is.

## Ingebouwde self-test

`.audit/fixtures/sample-plugin` is een minimale veilige fixture. De bootstrap-request in `.audit/request.json` auditeert deze fixture om de volledige harness zelf te valideren.
