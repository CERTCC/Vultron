---
title: "A mirrored doc rots first in the column no test could ever hold — delete that column rather than syncing it harder"
type: learning
timestamp: "2026-09-18T15:00:00Z"
source: ISSUE-3337
signal: theme-candidate
---

Two tables in this repo mirrored the same code inventory — the case-ledger
invariant harness — and both had gone stale. The instructive part is not *that*
they drifted but **which parts of them drifted**. In both, the columns that
source code can answer stayed roughly right, and the columns that only a demo
run can answer were wholly wrong:

| Column | Answerable from source? | State found |
|---|---|---|
| Test function name | yes | mostly right; missing later additions |
| `xfail` vs. active | yes (read the marker) | wrong for 7 rows |
| Which layer to check first | yes (it is a fixed rule) | right |
| Per-actor ✅/⚠️ pass/fail | **no** | wrong for every row |
| "Resolving issue" | **no** (a claim about the future) | all three issues closed |

The two unanswerable columns are the ones that were 100% wrong. That is not
coincidence: a fact nothing can check is a fact nobody does check. The
`xfail` column at least *could* have been ratcheted and merely wasn't; the
pass/fail column could not be ratcheted by construction, because it records the
outcome of one container run on one day.

So the reflex — "the table is stale, resync the table" — is the wrong move for
half the table. Resyncing an unratchetable column buys one correct day and
re-arms the trap. The move is to **stop stating it**: say what source can
answer, name where the live answer lives (here, the CI run), and delete the
rest. Applied to #3337 this retired one of the two tables outright rather than
fixing it, and narrowed the survivor's `Status` column from "is it passing?" to
"is it `xfail`ed, and who owns that?" — which a test now enforces.

A second, sharper symptom of the same root: the stale rows did not read as
uncertain. Every one carried a specific issue number, which is what made them
*actively* harmful rather than merely absent — an agent triaging a red job was
routed to #789, closed long ago, instead of to the layer that broke. An
unratcheted doc does not decay into silence; it decays into confident wrong
answers, which cost more than no doc.

**How to apply.** When you are about to sync a doc table against code, sort its
columns into ratchetable and not, *before* editing:

- **Ratchetable** (derivable from source, specs, or config): keep it, and add
  the ratchet in the same PR. Writing the table without the test is what
  produced this issue; the repo already had the pattern to copy
  (`test_universal_event_types.py`, `test_codebase_docs_paths.py`).
- **Not ratchetable** (a runtime outcome, a schedule, a forecast, a count that
  changes under you): delete it and point at whatever holds the live answer. If
  you cannot bring yourself to delete it, that is a signal the doc is trying to
  be a dashboard, and a dashboard in git is always stale.

Note this refines MS-16-001 ("never restate counts in long-lived docs") from a
rule about *counts* to a rule about *unverifiable state generally* — a count is
just the most common instance. The generalised test is "could a test fail on
this sentence?", not "is this a number?".

Corroboration needed: one instance so far, though it is a two-witness instance
in miniature (two independent tables, same discriminator, same outcome). A
second witness would be any session that finds a stale doc table where the
unverifiable columns are the wrong ones — or, as a negative witness, one where
a ratchetable column rotted while an unratchetable one stayed accurate, which
would falsify the ordering claim.

Related: neither queued entry covers this.
[[20260916-3192-tightening-a-resolver-wakes-dormant-checks]] is about a dormant
*check* that had never run; this is about a dormant *claim* that no check could
run against. The two share a shape worth watching: an assertion that looks load
bearing, is inert, and is trusted anyway.
