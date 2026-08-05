---
source: ISSUE-1953
timestamp: '2026-08-04T13:29:57.839639+00:00'
title: DeploymentMonitoringBundle shared base + DeployMitigationCallOutBundle
type: implementation
---

## Issue #1953 — DeploymentMonitoringBundle shared base + DeployMitigationCallOutBundle

Implemented and merged via PR #1964: <https://github.com/CERTCC/Vultron/pull/1964>

### Completion summary

All 5 acceptance criteria satisfied:

- **AC-1**: `DeploymentMonitoringBundle` frozen `@dataclass` created in `vultron/core/behaviors/call_out/bundles/deploy_monitoring.py` with three shared fields (`prioritize_deployment_factory`, `monitoring_requirement_factory`, `monitor_deployment_factory`), all defaulting to `AlwaysSucceed` per BT-23-002 ceiling rule.
- **AC-2**: `DeployFixCallOutBundle` refactored to inherit `DeploymentMonitoringBundle`; three duplicate field definitions removed; only `deploy_fix_factory` (AlwaysFail, p=0.10) retained.
- **AC-3**: `DeployMitigationCallOutBundle(DeploymentMonitoringBundle)` added in `vultron/core/behaviors/call_out/bundles/deploy_mitigation.py` with three mitigation-specific fields and `DEPLOY_MITIGATION_DETERMINISTIC` singleton.
- **AC-4**: `DEPLOY_MITIGATION_STOCHASTIC` singleton added in `vultron/demo/fuzzer/bundles/deploy_mitigation.py`, wiring all six fuzzer nodes from `report_management/deploy_fix.py`.
- **AC-5**: Full test coverage in `test/core/behaviors/call_out/test_deploy_monitoring_bundles.py` (32 new tests across 4 test classes).

### Validation

- 9 files changed: 593 insertions, 21 deletions
- 6079 tests pass, 0 failures
- black, flake8, mypy, pyright all clean
- Pre-PR code review: no FAIL findings
