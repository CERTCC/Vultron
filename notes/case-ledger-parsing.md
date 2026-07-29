---
title: Case Ledger JSONL Parsing — State Extraction and Tolerant Parsing Patterns
status: active
description: >
  Guidance for consumers of case-ledger JSONL: the three nesting shapes for
  RM/EM/VFD/PXA state, flat legacy wire spellings, and tolerant parsing patterns
  that degrade gracefully on malformed fields.
related_specs:
  - specs/case-ledger-processing.yaml
  - specs/demo-report.yaml
related_notes:
  - notes/case-ledger-authority.md
  - notes/sync-ledger-replication.md
relevant_packages:
  - vultron/core/behaviors/sync
  - vultron/demo/report.py
  - test/ci/invariants/common.py
---

# Case Ledger JSONL Parsing — State Extraction and Tolerant Parsing Patterns

## Three Nesting Shapes for RM/EM/VFD/PXA State

When distilling `RM`, `EM`, `VFD`, or `PXA` state from a case-ledger entry's
`payloadSnapshot`, the state value may appear in any of three shapes that all
occur in real devlogs:

### Shape 1 — ADR-0036 Dimension Objects (current canonical form)

Status fields are nested objects on `ParticipantStatus` or `CaseStatus`:

```json
{"rm": {"state": "ACCEPTED"}, "vfd": {"state": "VFd"}}
{"em": {"state": "ACTIVE"}, "pxa": {"state": "Pxa"}}
```

### Shape 2 — Legacy Flat Wire Spellings

Older log files use flat camelCase or snake_case state fields:

```json
{"rmState": "CLOSED", "vfdState": "VFD"}
{"rm_state": "ACCEPTED", "vfd_state": "VFd"}
```

The status models' `_migrate_flat_fields` validators accept these, so historical
logs contain them.

### Shape 3 — Nested Under an `Add` Activity

The status object is often nested as `payloadSnapshot["object"]` (or
`"object_"`), and a `CaseStatus` may be nested further under
`payloadSnapshot["object"]["caseStatus"]`:

```json
{
  "type": "Add",
  "object": {
    "type": "CaseStatus",
    "em": {"state": "ACTIVE"}
  }
}
```

## Robust Extraction Pattern

The recommended approach is a small recursive "candidate dicts" collector
that walks `object` / `object_` / `caseStatus` / `case_status` from the
snapshot root, then a per-dimension extractor that checks
`{key: {"state": ...}}` first and falls back to each flat alias.

This mirrors the defensive accessors already in
`test/ci/invariants/common.py` (`participant_status_identity_and_rm`,
`cs_observations_from_snap`) but generalises them for a single dimension.

```python
def _candidate_dicts(snap: dict) -> list[dict]:
    """Walk object/object_/caseStatus/case_status from snapshot root."""
    candidates = [snap]
    for key in ("object", "object_"):
        if isinstance(snap.get(key), dict):
            inner = snap[key]
            candidates.append(inner)
            for cs_key in ("caseStatus", "case_status"):
                if isinstance(inner.get(cs_key), dict):
                    candidates.append(inner[cs_key])
    return candidates

def _extract_dimension(candidates: list[dict], dim: str) -> str | None:
    """Extract state for dim (e.g. 'rm', 'em', 'vfd', 'pxa') from any shape."""
    flat_aliases = {
        "rm": ("rmState", "rm_state"),
        "em": ("emState", "em_state"),
        "vfd": ("vfdState", "vfd_state"),
        "pxa": ("pxaState", "pxa_state"),
    }
    for d in candidates:
        # ADR-0036 shape: {"rm": {"state": "ACCEPTED"}}
        if isinstance(d.get(dim), dict) and "state" in d[dim]:
            return d[dim]["state"]
        # Flat alias shapes
        for alias in flat_aliases.get(dim, ()):
            if alias in d:
                return d[alias]
    return None
```

## Tolerant Field Parsing

Confirm real shapes by dumping `ParticipantStatus` / `CaseStatus` with
`model_dump(by_alias=True)` — dimension objects serialize as
`{"rm": {"state": ...}}`, not flat `rmState`.

Two common malformed fields that must be tolerated to avoid aborting on a
single bad entry:

- **Corrupt `logIndex`**: coerce with `int(...)` wrapped in a helper that
  returns a fallback (e.g., `-1`) on `ValueError`.
- **Non-string `payloadSnapshot.actor`**: some entries carry an inline actor
  object (`{"id": "...", "type": "Actor"}`). Extract `actor["id"]` when the
  field is a dict.

These tolerant parsers allow one malformed row to degrade a single timeline
entry rather than propagating as an uncaught exception through the
`ReportError` boundary.

## Multi-Case Partitioning (DRPT-02-006)

When case-ledger JSONL entries span more than one case (distinct `case_id`),
a consumer MUST:

1. Group by `case_id` before constructing any timeline.
2. Order within each group by `(case_id, log_index)`.
3. Compute replica-presence matrices per case, not globally.

`log_index` restarts at 0 for each case, so a merged multi-case timeline
produces interleaved `0, 0, 1, 1, …` orderings that misrepresent chronology.
Same-named actor directories (`finder`, `vendor`) recur across demos and would
collapse into one presence column if not partitioned.

This is captured in `specs/demo-report.yaml` DRPT-02-006.

## References

- `notes/case-ledger-authority.md` — ledger authority model and `payloadSnapshot` criteria
- `specs/case-ledger-processing.yaml` CLP-07 — canonical entry criteria
- `specs/demo-report.yaml` DRPT-02-006 — multi-case partitioning requirement
- `test/ci/invariants/common.py` — existing defensive extraction helpers
- `vultron/demo/report.py` — reference implementation using this pattern

*Sources: ISSUE-1307, PR-1604,
`plan/incoming/learnings/20260722-ledger-jsonl-dimension-state-shapes.md`,
`plan/incoming/learnings/20260722-demo-report-multi-case-partitioning.md`.*
