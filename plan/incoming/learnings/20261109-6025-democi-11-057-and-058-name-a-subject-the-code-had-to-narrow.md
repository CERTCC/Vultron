---
title: "DEMOCI-11-057 and DEMOCI-11-058 each name a subject the implementation had to narrow, and the narrowing is a judgment neither records"
type: learning
timestamp: "2026-11-09T18:40:00Z"
source: ISSUE-6025
signal: spec-ambiguity
---

**Trigger.** You are extending the demo base-versus-head comparison — the
normalizer in `vultron/demo/recordings/traces.py` or the read attribution in
`vultron/demo/recordings/runner.py` — and you need to know whether some value
is in its subject. Or a reviewer reads the code as narrower than the
requirement it cites.

**Claim.** Two requirements name a subject in a word that admits a wider and a
narrower reading, and the wider one is both legal and worse. `learn` should
settle which each means, in the requirement rather than in a docstring.

1. **DEMOCI-11-058, "relabel every id by its first appearance."** An actor URI
   is an id. It is also fixed by the cast (DEMOCI-11-020), so it cannot shift
   between two runs, and relabelling it costs the reader the one name in a
   ledger diff that says *who*. #6025 relabels only the UUIDs a run draws and
   says so in the module docstring. Is "every id" every id, or every id a run
   draws?
2. **DEMOCI-11-057, "the cast members whose containers it read."** Every
   container call of an in-process run goes through one routed client, reads
   and acts alike. Counting an act would put a cast member in a step's `reads`
   that the step wrote to; not counting it means an act redirected to another
   container shows only in the ledger trace. #6025 counts only `GET`. Is
   "read" any container call, or a read?

**Evidence.** Both narrowings were made in #6025 (PR #6146) and both were
raised by its pre-push review as possible spec deviations — the second one
with a captured `rv` trace showing `step | Reporter submits vulnerability
report … | reads=actor0`, where nothing was read. Each rests on a docstring
sentence today, so the next change to either file re-derives the judgment.

**The question for `learn`.** For each, either reword the requirement to the
narrow subject ("every id a run draws", "the cast members whose containers it
read, a read being a `GET`"), or keep the wide subject and record why the
narrow implementation satisfies it. A third requirement may be the cleaner
answer for the second one: say that the check tree records reads and the
ledger records acts, which is what makes the pair of traces complementary
(DEMOCI-11-055).

**How to apply meanwhile.** Read the two docstrings before changing either
file, and keep them as the statement of subject until the requirements carry
it.
