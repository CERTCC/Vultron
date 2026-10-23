---
source: ISSUE-1656
timestamp: '2026-07-24T15:32:22.432264+00:00'
title: 'Refactor demo CI: separate invariant-harness job + per-scenario event-type
  lists'
type: implementation
---

## Issue #1656 — Refactor demo CI: separate invariant-harness job + comprehensive per-scenario event-type lists

Implemented all three ACs:

- **AC-1 (DEMOCI-04-001–04-003)**: Moved the invariant harness out of the `demo` job into a separate `invariant-harness` job with `needs: demo` + `if: always() && !startsWith(github.head_ref, 'dependabot/')`. Each scenario now has two independent CI status checks.
- **AC-2 (DEMOMA-16-001–16-008)**: Expanded all six `_XXX_EXPECTED_EVENT_TYPES` constants beyond the four universal types to include scenario-specific phases (invite_actor_to_case, offer_case_participant, accept_invite_actor_to_case per scenario).
- **AC-3 (DEMOCI-04-004)**: Added `test_fvcv_extension_offer_case_participant_present` to cover the ADR-0026 suggest-actor flow in the FVCV-extension scenario.

PR: <https://github.com/CERTCC/Vultron/pull/1666>
