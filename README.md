# Programmeren - WordPress Plugin Audit Harness

Centrale, op aanvraag gestarte auditomgeving voor WordPress-plugins.

## Doel

De harness voert voor iedere plugin een generieke WordPress-audit uit en activeert daarnaast alleen de gespecialiseerde tooling die hoort bij een gevalideerd pluginprofiel.

De generieke `base`-audit bevat waar toepasbaar:

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
- gecontroleerde generieke WordPress-runtime via `wp-env`;
- source-snapshot ZIP + SHA-256;
- auditlogs en rapporten als GitHub Actions artifact.

De centrale audittooling gebruikt exact gepinde versies. De door Composer opgeloste audit-dependencygraph moet bovendien exact de vastgelegde SHA-256 matchen; stille dependencydrift blokkeert de run.

## Plugin-aware profielen

`.audit/profiles/index.json` is de uitvoerbare registry voor pluginherkenning. De router werkt fail-closed:

1. de doelrepository wordt uitgecheckt;
2. `.audit/scripts/resolve_profile.py` vergelijkt de repository en geregistreerde plugin-identiteit met de bindings;
3. bij precies één geldige match wordt dat profiel gekozen;
4. bij geen match wordt uitsluitend `base` gebruikt;
5. bij conflicterende matches stopt de audit;
6. gespecialiseerde services, PHP-extensies, WordPress-plugins, browsertooling, provider-mocks en probes worden alleen gestart vanuit het gekozen profiel.

De resolver schrijft `audit-results/profile-resolution.json` met profiel, matchmethode, capabilities, runtimeconfiguratie en een SHA-256 fingerprint. Voor een gespecialiseerde runtime wordt het profiel in een tweede job opnieuw opgelost en moet dezelfde fingerprint terugkomen voordat uitvoering begint.

Structuur:

```text
.audit/profiles/
  index.json
  base.json
  categories/
    cache.json
  plugins/
    ultracache-pro.json
```

### Huidig gespecialiseerd profiel

`ultracache-pro` erft van `cache` en activeert alleen voor UltraCache Pro de extra cache/runtime-capabilities, waaronder Redis, APCu, MySQL, WooCommerce, Playwright/concurrencyprobes en de gecontroleerde Cloudflare-provider mock. Andere plugins krijgen deze onderdelen niet.

Nieuwe plugins krijgen een eigen profiel wanneer ze werkelijk andere gespecialiseerde tooling nodig hebben. Voeg die tooling niet toe aan `base` alleen omdat één plugin haar nodig heeft.

## Canoniek ChatGPT-contract

`.audit/contract.json` is de machineleesbare projectafspraak voor de ChatGPT-route. Het legt vast wanneer deze harness wel en niet wordt gebruikt, welk requestschema geldt, welke repository- en veiligheidsgrenzen gelden, hoe profielen worden opgelost en hoe een run na de request-write wordt teruggevonden en beoordeeld.

De beslisregel is:

- expliciete plugin-test/audit + expliciet geïdentificeerde GitHub-repository + bruikbare GitHub-apprechten -> deze centrale harness;
- gewone repository-inspectie of advies -> geen audittrigger;
- losse ZIP, lokale map of geplakte code zonder GitHub-target -> lokale/meegeleverde auditroute, niet deze harness;
- private doelrepository terwijl deze harness public is -> fail-closed blokkeren;
- onbekende plugin -> base-audit, zonder product-specifieke tooling.

## Starten

### Handmatig in GitHub

Ga naar **Actions -> Full WordPress Plugin Audit -> Run workflow** en vul minimaal `target_repo` in als `owner/repository`.

### Via ChatGPT

Als jij zegt **"test deze plugin"**, **"audit deze plugin"** of een equivalente expliciete auditopdracht geeft voor een geïdentificeerde GitHub-pluginrepo, schrijft ChatGPT via de gekoppelde GitHub-app de gewenste auditrequest naar `.audit/request.json`.

Alleen een wijziging van dat bestand op `main` start de automatische ChatGPT-route. Gewone pushes naar andere bestanden en pull requests starten geen runnerjob.

ChatGPT hoort daarbij:

1. doelrepo/ref/pad eerst te verifiëren;
2. de huidige `.audit/request.json` inclusief blob-SHA te lezen;
3. voor iedere run een unieke `request_id` te schrijven;
4. alleen `.audit/request.json` atomair op `main` bij te werken;
5. de commit-SHA van die write te bewaren en readback te controleren;
6. de `Full WordPress Plugin Audit`-run met exact die head-SHA te volgen;
7. jobs, artifacts, profielresolutie en relevante evidence te lezen;
8. scannerhits als kandidaat-findings aan `wordpressqualityarchitect` terug te geven, niet automatisch als bevestigde bugs.

Voorbeeld request:

```json
{
  "request_id": "2026-08-17-example",
  "target_repo": "owner/plugin-repository",
  "target_ref": "main",
  "target_path": ".",
  "run_runtime": true,
  "php_version": "8.3"
}
```

## Publiek versus prive

Deze harness-repository is momenteel **public**. Daarom weigert de workflow fail-closed om een **private** doelrepository te auditen: logs en artifacts zouden anders private code of findings kunnen lekken.

Wil je later private plugins auditen, maak deze harness eerst private en voeg daarna zo nodig een read-only repositorytoken toe als Actions secret `PLUGIN_REPO_TOKEN`.

## Bewijsgrens

Een groene run bewijst alleen de werkelijk uitgevoerde statische, generieke runtime- en eventueel profiel-specifieke controlled-runtime checks. Het is geen vervanging voor echte staging, productie-observatie, volledige browser/device-matrix, live betaalproviders of menselijke toegankelijkheidstests.

## Veiligheid

- De workflow heeft standaard alleen `contents: read`.
- De ChatGPT-trigger vereist schrijfrecht op `.audit/request.json`; publieke bezoekers kunnen de audit daardoor niet starten.
- Credentials worden niet in artifacts opgenomen.
- Het doelproject wordt niet gewijzigd of teruggeschreven.
- Projectafhankelijkheden worden voor statische/dependencychecks niet met eigen Composer-scripts/plugins uitgevoerd.
- Runtime-uitvoering gebeurt alleen wanneer `run_runtime=true` is gekozen.
- Specialized runtimecode komt uitsluitend uit deze harness-repository, niet uit het doelproject.
- Onbekende plugins kunnen geen gespecialiseerde tooling activeren.
- Scannerhits zijn kandidaat-findings; `wordpressqualityarchitect` bepaalt pas na bewijs of iets een bevestigde bug is.

## Ingebouwde self-test

`.audit/fixtures/programmeren-audit-fixture` is een minimale veilige fixture. `.audit/request.json` is tegelijk het gecontroleerde ChatGPT-triggerbestand en bevat per run een unieke `request_id`.
