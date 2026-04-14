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

---

### 2026-04-09 EMBARGO-DUR-1 completed

`EmbargoPolicy` now uses `timedelta` internally and ISO 8601 duration strings
at the wire layer. Key notes:

- `isodate.parse_duration("P2W")` returns `timedelta(weeks=2)` — a
  `timedelta` — so week rejection requires an explicit pre-check for `W` in
  the date part of the duration string before calling `isodate`.
- `isodate.parse_duration("P1Y")` returns `isodate.Duration` (not `timedelta`)
  so year/month rejection is handled by checking `isinstance(parsed, timedelta)`.
- `object_to_record()` serializes `timedelta` fields as ISO 8601 strings
  (via `field_serializer(when_used="json")`). The DataLayer round-trip
  works correctly because `TinyDbDataLayer` stores serialized JSON and
  `model_validate` re-parses via the `field_validator`.
- Test helpers that pass ISO 8601 strings to `EmbargoPolicy(...)` must use
  `cast(Any, EmbargoPolicy)(...)` to satisfy mypy (field is typed `timedelta`
  but Pydantic accepts strings at runtime via the `field_validator`).

---

### 2026-04-11 SYNC-1 completed

**`CaseLogEntry` / `CaseEventLog`**:

- `CaseLogEntry` is a plain Pydantic `BaseModel` (not frozen).
  Immutability of the append-only log is enforced by `CaseEventLog`; the
  model itself is not frozen so that the `model_validator` can compute
  `entry_hash` via `model_validator(mode="after")` without hitting a
  frozen-model assignment error.
- `entry_hash` is excluded from the content that is hashed (to avoid a
  self-referential dependency). The `_hashable_dict()` method explicitly
  lists the fields included in the canonical form; adding new fields
  requires updating both `_hashable_dict()` and existing log data
  (hash-chain break risk).
- Canonical serialisation uses `json.dumps(sort_keys=True, separators=(',', ':'),
  default=str)` — RFC 8785 JCS-compatible and Merkle-tree forward-compatible
  (SYNC-01-005). `default=str` handles `datetime` and enum values.
- `tail_hash` is based on the last **recorded** entry only; rejected entries do
  not advance the hash chain for replication purposes (CLP-04-003).
- `verify_chain()` validates: hash integrity of each entry, correct
  `prev_log_hash` linkage for recorded entries, and sequential `log_index`.

**BTBridge leadership guard**:

- `is_leader` is an injectable `Callable[[], bool]`; single-node default
  always returns `True`. The seam is there for multi-node Raft; the default
  imposes zero runtime cost on existing code.
- Existing callers of `BTBridge(datalayer=...)` are unaffected since
  `is_leader` is a keyword-only argument with a default.

**Next step**: SYNC-2 — one-way log replication to Participant Actors via
`Announce(CaseLogEntry)`. Prereqs: SYNC-1 ✅, OUTBOX-MON-1 ✅,
D5-7-TRIGNOTIFY-1 ✅.

---

### 2026-04-14 Plan refresh #73 gap analysis

**Completed since last refresh (2026-04-08)**:
D5-7-BTFIX-1 ✅, D5-7-BTFIX-2 ✅ (BT cascade violations; commit `0b8fa4c6`),
D5-7-TRIGNOTIFY-1 ✅ (trigger activities populate `to` field),
D5-7-DEMONOTECLEAN-1 ✅ (add-note-to-case uses trigger API; commit `1a89d7dd`),
SYNC-2 ✅ (Announce(CaseLogEntry) replication; commit `4268549d`),
SYNC-3 ✅ (full sync loop with retry/backoff; commit `25babfd6`),
SYNC-TRIG-1 ✅ (sync-log-entry trigger endpoint; commit `2af8a85e`),
D5-7-DEMOREPLCHECK-1 ✅ (finder replica verification; commit `2af8a85e`),
PRIORITY-325 DL-SQLITE ✅ (TinyDB→SQLite migration; commit `c9316e30`).

**Test count**: 1402 passed, 13 skipped (post DL-SQLITE migration). Count is
lower than the 1544 high-water mark after SYNC-TRIG-1 because the TinyDB
backend test file was replaced with a SQLite equivalent during PRIORITY-325.

**DL-SQLITE ADR**: ADR number is 0016 (not 0015 as the original plan task
body stated). Fixed in IMPLEMENTATION_PLAN.md.

**Stale references to archived notes** (DOCMAINT-2 task added):
Commit `0922e1f1` archived several notes files; corresponding cross-references
in `plan/`, `specs/`, and `notes/` still point to old paths. DOCMAINT-2
added to Phase PRIORITY-350 to track the cleanup.

**Only open items after this refresh**:
DOCMAINT-2 (new), D5-7-HUMAN (sign-off, agents must not mark), SYNC-4
(multi-peer sync), TOOLS-1 (Python 3.14), DOCS-3 (user-stories trace),
CONFIG-1 (YAML config).
