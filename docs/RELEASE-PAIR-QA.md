# WordPress release-pair QA

Generic execution adapter for paired WordPress theme and plugin testing. Owned by wordpressqualityarchitect under webactueel-workflow. It does not own client projects or grant production approval.

## Existing roles

- Yolol100/programmeren: existing static/plugin/security scanner workflow (WPCS, Semgrep, Trivy, Gitleaks, Plugin Check and more).
- This new reusable pair workflow: optional real WordPress/MariaDB activation and upgrade of a theme + plugin.
- Yolol100/Designchecker: authorized website browser, Lighthouse, axe and visual regression.
- Yolol100/seochecker: public technical SEO, links and canonicals.
- website-qa-checklist: final staging acceptance, no automatic production GO.

## Use from an authorized PRIVATE project repository

The private caller must first upload one GitHub Actions artifact containing theme.zip, plugin.zip and optionally previous-plugin.zip. It can then invoke the public reusable workflow:

    jobs:
      qa:
        needs: package
        uses: Yolol100/programmeren/.github/workflows/wordpress-release-pair.yml@main
        with:
          evidence_id: theme-plugin-php83
          release_artifact: private-release-pair
          theme_archive: theme.zip
          plugin_archive: plugin.zip
          previous_plugin_archive: previous-plugin.zip
          php_version: '8.3'
          plugin_check: true
          lighthouse_lab: false

The `evidence_id` must be unique per reusable-workflow invocation in a caller run; use a distinct label for each PHP matrix value or release pair. Evidence names also include the run attempt. The harness is checked out at the exact commit containing the selected reusable workflow. WordPress core is pinned to `7.1.4`, MariaDB to `11.4.13`, and Plugin Check to `2.1.0`; actual runtime versions are collected separately in evidence. Upgrade checks use Plugin Check `update` mode, and fresh installations use `new` mode.

The sample assumes a separate caller-owned package job. If no previous release is available, omit previous_plugin_archive: the upgrade check is explicitly NOT_RUN.

## What gets executed

1. Validate supplied ZIP paths, slugs, structure, checksums and WordPress metadata.
2. Run pinned official WordPress wp-env on Docker/MariaDB with the theme and plugin mounted.
3. Verify WordPress core bootstrap, database connection and both package activations.
4. Create a synthetic editor-authored page and meta sentinel.
5. When an approved previous plugin is supplied, deactivate, replace in the same mount and reactivate the candidate twice.
6. Check the synthetic content survives. Optionally execute official Plugin Check and isolated Lighthouse lab.
7. Keep sanitized run-scoped results within the private caller's Actions artifacts, then destroy the test containers.

A clean synthetic installation does not prove an actual customer DB migration, complete editor roundtrip, real translation-provider functionality, real reviews, staging hosting parity, or Lighthouse of a fully populated live site.

## Local contract verification

    python3 script/test-release-pair.py
    python3 -m py_compile script/release-pair-prepare.py
    bash -n script/release-pair-runtime.sh

## Important boundaries

Never commit client ZIPs, database dumps, reviews, contact details, tokens, customer screenshots or audit results to public branches. Do not turn the existing public-only plugin-scanner workflow into a private-target importer. The new pair workflow accepts an artifact only from the caller's own workflow run, not arbitrary external URLs. No background site deployment, secrets, permissions changes or automatic merges are performed.

Automated Lighthouse on an isolated, unpopulated WordPress page is not a production performance measurement. Run Designchecker and seochecker on an authorized, populated staging URL. Mark tests without the needed runtime as NOT_RUN.
