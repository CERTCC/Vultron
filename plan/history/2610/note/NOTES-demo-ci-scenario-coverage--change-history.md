---
source: NOTES-demo-ci-scenario-coverage--change-history
timestamp: '2026-10-12T23:50:06.960301+00:00'
title: 'Demo CI scenario coverage: change history and ISSUE-1996 corrections'
type: note
---

Archived from `notes/demo-ci-scenario-coverage.md` by #4497 (notes sweep): a
PR-by-PR change-history list and the ISSUE-1996 correction bullets record past
states, not guidance (NF-08-004). Superseded by: the scenario registry and its
generated `.github/demo-scenarios.json` (ADR-0098, DEMOCI-11-004), and the
ratcheted tables that remain in `notes/demo-ci-scenario-coverage.md`
(DEMOCI-11-007).

---

## Archived content

- `fccv-extension` spec entry DEMOMA-16-010 was added as part of ISSUE-1996;
  the test constant was already correct.
- `fvv`, `fvcv-extension`, and `fcv` were missing `accept_invite_actor_to_case`
  from their `_EXPECTED_EVENT_TYPES` lists; corrected as part of ISSUE-1996 (AC-2).
- `fcvcv`, `fvcv-extension`, and `fccv-extension` were missing
  `accept_actor_recommendation`; corrected as part of ISSUE-1996 (AC-2 follow-up).
- `fcv-reject` (DEMOMA-16-011) was added as part of IDEA-1218 planning.

### Change history

Statements here record past states and are exempt from the no-restated-count
rule (DEMOCI-11-008), which is why the exemption is keyed on this heading.

- PR #2030 added the `push: branches: ["main"]` trigger and marked `fv`,
  `fvcv-handoff` and `fcvcv` as `full_suite_only: false`, leaving the rest
  full-suite-only.
- PR #2084 (IDEA-1218) implemented `fcv-reject` and added it as a matrix entry
  with `full_suite_only: false` (DEMOCI-03-002). Full-suite scenario list
  updated from 8 to 9 scenarios.
- PR #3464 (ISSUE-3450) made the matrix a generated projection of the scenario
  registry, so the entries are no longer hand-maintained here or in the
  workflow (ADR-0098).
- PR #4397 (ISSUE-2073, ISSUE-2074) ran the DEMOCI-07-003 follow-up analysis
  after both embargo scenarios were passing in CI. The PR set needed no new
  member; DEMOCI-06-002 was amended to list `activate_embargo_on_case` among
  the event types it covers and to explain the two embargo members.
