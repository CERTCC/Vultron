## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

---

## `notes/state-machine-findings.md` completion-status section is aspirational

The "Completion Status" table in section 9 of
`notes/state-machine-findings.md` lists commit hashes (`fix-em-wire-boundary`,
`refactor-em-propose`, `refactor-em-terminate`, etc.) that do **not** appear
in the actual git history. The corresponding code changes **are** in the
codebase (OPP-01, OPP-02, OPP-03, OPP-07 partial, OPP-08 via P90-1, OPP-09
minimum step via P90-2), but they were committed under different names or
bundled into the P90 work. The "Status: Refactoring complete — all P and OPP
items addressed" header is broadly correct but the commit references are
inaccurate. A future refresh of that file should replace the fictional commit
hashes with the actual git log references or remove them.

OPP-05 (consolidate duplicate participant RM helpers) is explicitly NOT done
— two near-duplicate functions remain:

- `_find_and_update_participant_rm()` in `vultron/core/behaviors/report/nodes.py`
- `update_participant_rm_state()` in `vultron/core/use_cases/triggers/_helpers.py`
This is captured as TECHDEBT-39 in `plan/IMPLEMENTATION_PLAN.md`.

---

## `dl.save()` is the canonical persistence pattern for core code

After TECHDEBT-32b, `dl.save(obj)` is the **sole** approved pattern for
persisting domain objects from core code:

```python
# Correct
dl.save(case)
dl.save(participant)
dl.save(actor_obj)

# Now removed from codebase (do not reintroduce):
dl.update(obj.as_id, object_to_record(obj))   # core importing adapter
save_to_datalayer(dl, obj)                      # redundant core helper
```

The `save_to_datalayer()` helper has been deleted. The `object_to_record`
import from adapter is banned in core. Future core/BT code must use
`dl.save(obj)` exclusively.

TECHDEBT-32c remains open: `vultron/wire/as2/rehydration.py` imports
`get_datalayer` from the TinyDB adapter as a fallback — this is a
wire-imports-adapter violation to be fixed separately.

---

## TECHDEBT-34 complete: EM state machine guards added

Three unguarded `em_state = EM.ACTIVE` sites in `vultron/core/use_cases/` now
have explicit guards:

- **Trigger-side** (`SvcEvaluateEmbargoUseCase`): machine adapter raises
  `VultronConflictError` on invalid state.
- **Receive-side** (`AddEmbargoEventToCaseReceivedUseCase`,
  `AcceptInviteToEmbargoOnCaseReceivedUseCase`): `is_valid_em_transition()`
  check with WARNING log; proceeds regardless (state-sync override pattern).

All `rm_state=RM.XXX` in core are constructor args for new status objects, not
transitions — documented justification for bypassing machine guard. The
`append_rm_state()` guard already enforces validity for all RM mutation paths.

---

##
