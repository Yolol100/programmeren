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

De centrale audittooling gebruikt exact gepinde versies. De door Composer opgeloste audit-dependencygraph moet bovendien exact de vastgelegde SHA-256 matchen; stille dependencydrift blokkeert de run.

## Starten

### Handmatig in GitHub

Ga naar **Actions → Full WordPress Plugin Audit → Run workflow** en vul minimaal `target_repo` in als `owner/repository`.

### Via ChatGPT

Als jij zegt **"test deze plugin"**, maakt ChatGPT via de gekoppelde GitHub-app één tijdelijk issue met een titel die begint met `[audit]` en een JSON-body zoals hieronder. Alleen een `[audit]`-issue dat door de eigenaar van deze repository is aangemaakt mag de runnerjob starten. Gewone pushes, pull requests en andere issues starten geen runnerjob.

Voorbeeld issue-body:

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
- De ChatGPT issue-trigger is owner-only.
- Credentials worden niet in artifacts opgenomen.
- Het doelproject wordt niet gewijzigd of teruggeschreven.
- Projectafhankelijkheden worden voor statische/dependencychecks niet met eigen Composer-scripts/plugins uitgevoerd.
- Runtime-uitvoering gebeurt alleen wanneer `run_runtime=true` is gekozen.
- Scannerhits zijn kandidaat-findings; `wordpressqualityarchitect` bepaalt pas na bewijs of iets een bevestigde bug is.

## Ingebouwde self-test

`.audit/fixtures/programmeren-audit-fixture` is een minimale veilige fixture. `.audit/request.json` blijft als voorbeeld/configuratiesnapshot aanwezig; de daadwerkelijke ChatGPT-trigger gebruikt een owner-only `[audit]`-issue zodat de GitHub-koppeling de run betrouwbaar kan starten.
