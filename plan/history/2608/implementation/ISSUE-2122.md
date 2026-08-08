---
source: ISSUE-2122
timestamp: '2026-08-08T01:24:06.423918+00:00'
title: 'fix: scenario ratchet broken — DEMO= source moved to demo-scenarios.json'
type: implementation
---

Issue #2122: two tests in `test_integration_script_scenarios.py` failed on clean `origin/main` — the CI-side extractor grep'd for `DEMO=` lines in `demo-integration.yml`, but PRs #2118/#2119 had moved the scenario matrix to `.github/demo-scenarios.json`. Fixed `_ci_scenarios()` to parse the JSON file instead, added `_CI_SCENARIOS_JSON` path constant, and added two new structural-validation guards (`test_ci_scenarios_json_exists`, `test_ci_scenarios_json_is_valid`) satisfying DEMOCI-08-002. PR: <https://github.com/CERTCC/Vultron/pull/2123>
