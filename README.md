# Programmeren – WordPress Plugin Audit Harness

Centrale, handmatig gestarte auditomgeving voor WordPress-plugins.

## Doel

Eén GitHub Actions-run gebruikt één `ubuntu-latest` job en verzamelt meerdere onafhankelijke bewijslagen zonder automatisch bij iedere push of pull request te draaien.

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
- plugin-ZIP + SHA-256;
- auditlogs en rapporten als GitHub Actions artifact.

## Starten

### Handmatig in GitHub

Ga naar **Actions → Full WordPress Plugin Audit → Run workflow** en vul minimaal `target_repo` in als `owner/repository`.

### Via ChatGPT

ChatGPT kan `.audit/request.json` wijzigen. Alleen een wijziging van dat bestand triggert de audit automatisch. Normale wijzigingen, pushes en pull requests starten deze workflow niet.

Voorbeeld:

```json
{
  "request_id": "2026-08-15-example",
  "target_repo": "owner/plugin-repository",
  "target_ref": "main",
  "target_path": ".",
  "run_runtime": true
}
```

## Private pluginrepository

Voor een andere private repository is een read-only repositorytoken nodig in de Actions secret `PLUGIN_REPO_TOKEN`. Voor publieke repositories is dit niet nodig.

## Bewijsgrens

Een groene run bewijst alleen de uitgevoerde statische/controlled-runtime checks. Het is geen vervanging voor echte staging, productie-observatie, browser/device-matrix, betaalproviders of menselijke toegankelijkheidstests.

## Veiligheid

- De workflow heeft standaard alleen `contents: read`.
- Credentials worden niet in artifacts opgenomen.
- Het doelproject wordt niet gewijzigd of teruggeschreven.
- Projecttests worden alleen uitgevoerd wanneer zij veilig detecteerbaar zijn; dependency-installatie gebruikt waar mogelijk `--no-scripts`/`--no-plugins`.
- Alle auditresultaten zijn diagnostisch; een scannerhit is nog geen bevestigde bug.
