## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

---

### 2026-04-08 Plan refresh #72 gap analysis

**Test suite**: 1262 tests passing (refresh #72). No warnings, no
ResourceWarnings. All linters clean.

**D5-6-AUTOENG completed (2026-04-08)**: Invitation acceptance now
auto-advances the invitee to RM.ACCEPTED and queues `RmEngageCaseActivity`
without a separate trigger. Three-actor and multi-vendor demos no longer
issue manual `engage-case` calls. D5-6-CASEPROP is now focused solely on
`EmitCreateCaseActivity` (`create_case` BT) missing `to` field and full
case embedding.

**D5-6-EMBARGORCP dependency clarification**: Per `notes/protocol-event-cascades.md`,
Option 2 (remove standalone `Announce(embargo)`, rely on `Create(Case)`)
is recommended and is independent of IDEA-260408-01 ordering. Alternatively,
it can be deferred until IDEA-260408-01-4 removes `InitializeDefaultEmbargoNode`
from `validate_tree.py` entirely. The plan has been updated to capture both
paths.

**SYNC spec and CLP spec expansion (2026-04-08)**: `specs/case-log-processing.md`
(CLP) and `specs/sync-log-replication.md` were significantly expanded with
new requirements for:

- `CaseLogEntry` model fields: `log_index`, `disposition`, `term`
- Assertion intake path (CLP-01): ordinary inbound activities as participant
  assertions; CaseActor as sole canonical log writer
- Local audit log vs. replicated canonical chain (CLP-03, CLP-04)
- Canonical serialization for hash computation (SYNC-01-005; RFC 8785 JCS)
- Commit discipline (SYNC-09): emit-after-commit invariant
- Leadership guard port in BT bridge (SYNC-09-003)
SYNC-1 task description updated in IMPLEMENTATION_PLAN.md to capture all of
these. The old note about `prev_log_index` in SYNC-2 has been corrected to
`prev_log_hash` to match the hash-chain design.

**BUG-2026040102 (circular import in test_performance.py)**: Marked FIXED
2026-04-01 in BUGS.md. Test confirmed passing in isolation as of 2026-04-08.
Resolution section was never written; fix was applied as part of the April 1
multi-vendor demo work. BUGS.md updated with resolution note.

**Testing note (2026-04-08)**: When tests need to persist actor records
through `DataLayer.create`, use a concrete actor subtype such as
`as_Organization` rather than the base `as_Actor`; the base type's optional
`type_` conflicts with the `PersistableModel` protocol under pyright.

**CONFIG-1 (YAML config)**: IDEA-260402-01 (from `plan/IDEAS.md`) has been
added as a new PRIORITY-350 task. `pyyaml` is already a transitive dependency
(from docker-compose YAML parsing). The task is independent and can be
implemented any time after D5-7 sign-off.

**IDEA-260402-02 (per-participant case replica)**: Design captured in
`plan/IDEAS.md`. Implementation is the participant-side receive path for
`Announce(CaseLogEntry)` replication; this is SYNC-2 scope. Added to
Deferred section of IMPLEMENTATION_PLAN.md for visibility.
