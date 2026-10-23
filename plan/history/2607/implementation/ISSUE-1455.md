---
source: ISSUE-1455
timestamp: '2026-07-17T18:54:29.441066+00:00'
title: Migrate core/behaviors and core/use_cases — AC-2/3/4 named predicates and ValueError
  guards
type: implementation
---

## Issue #1455 — Migrate core/behaviors and core/use_cases to consume staged VulnerabilityCase types

Implemented AC-2, AC-3, AC-4. AC-1 and AC-5 deferred (wire/core type mismatch).

- AC-2: Fixed latent getattr bug — replaced getattr(case, "current_status", None) with try/except ValueError in ValidateCaseStatusTransitionNode.update(); extracted_resolve_em_state() helper with proper ValueError guard
- AC-3: Replaced em_state not in (EM.ACTIVE, EM.REVISE) with is_em_embargo_active(); added ValueError guard to ValidateEmbargoRevisionStateNode
- AC-4: Replaced pxa_state != CS_pxa.pxa with is_pxa_public_aware or is_pxa_exploit_public or is_pxa_attacks_observed; added ValueError guard to_pxa_embargo_ineligible()
- Pre-PR review found 3 correctness bugs (all same root: bare current_status access without ValueError guard); fixed all three before PR opened
- Tests: +10 vs baseline (5035 passed)

PR: <https://github.com/CERTCC/Vultron/pull/1497>
