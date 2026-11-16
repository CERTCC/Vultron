---
source: NOTES-case-event-history--read-the-canonical-copy-a-merge-reports-its-holes
timestamp: '2026-11-16T18:30:59.055697+00:00'
title: Read the Canonical Copy; a Merge Reports Its Holes
type: note
---

**Archived:** 2026-11-16
**Reason:** delivered and redundant — captured in CEH-02-003/004/006/009/010 and ADR-0174; code in vultron/measure/ledger/copies.py and ends.py. The corpus-gap table stays in the note as guidance

---

## Read the Canonical Copy; a Merge Reports Its Holes

Only the CASE_MANAGER's ledger is complete. A participant's replica stops receiving
entries while its embargo consent has lapsed and after its report closes
(CM-10-005, CM-23-004), so an event recorded in a gap it missed is absent from its
copy. Prefer that copy when the input holds it (CEH-02-004).

Identify it from the **entries**, never from the path (CEH-02-009). A recording's
ledger file is named for neither its actor nor its role: the committed recordings are
`ui/src/recordings/<scenario>/case-actor.jsonl`, while a demo run writes
`<actor>-case-ledger.jsonl` under a directory named for the actor. A path-derived
answer misreads the scenario name as the actor name, finds no CASE_MANAGER, and sends
every recording down the merge path to be reported as holed.

No entry names the copy's holder: a replica's entry is byte-identical to the
CASE_MANAGER's (CLP-07-013). So the layer identifies the copy by **completeness**: a
copy is read alone when it holds one entry at each index from `0` up with no gap
(CLP-14-010) and every entry hash any other copy of the case holds
(`vultron/measure/ledger/copies.py`). The CASE_MANAGER's copy always passes.

Completeness is known only relative to the input, so carry the end separately. A
replica cut off at the tail, as when its report closed, passes when no fuller copy is
handed over, and the result calls it a complete copy with no holes. `end_confirmed`
is set only when the entries prove nothing follows the last entry
(`vultron/measure/ledger/ends.py`). Two things prove it: the last entry is the
CASE_MANAGER's own closure (`closure_boundary_indices`, CM-23-013), or another copy
ends on the same entry. A measure that needs the whole case refuses a history whose
end is unconfirmed. Do not try to name the copy's holder: the entries cannot say it
(decided for #5779).

Two copies holding different entries at one index, or one entry hash with two
different bodies, are reported, never resolved: a conforming ledger has none, so a
history over one is not to be trusted, and keeping either body would pick by file
order. A bad row that names another case does not make a file's copy incomplete; only
a row that names no case might be the missing entry.

For the same reason the layer takes its files from the caller and globs for nothing
itself (CEH-02-003, CEH-02-010). `vultron-demo-report` keeps its own
`**/*-case-ledger.jsonl` discovery in `vultron/demo/report/timeline.py`, which
DRPT-01-007 pins; that glob matches none of the committed recordings, so a layer that
inherited it could not open its own test corpus.

A merge of participant replicas is the fallback, and it must report the log indices
no replica supplied (CEH-02-006). A measure over a history with a hole is wrong
rather than imprecise, so the caller needs to be able to refuse the history instead
of scoring it.

The committed canonical recordings under `ui/src/recordings/` are the test corpus:
each is the CASE_MANAGER's own copy of a real scenario run, with a step list beside
it. They cover an embargo termination, an embargo revision, a refused invitation and
several vendors.
