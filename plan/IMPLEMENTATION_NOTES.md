## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

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

