---
title: "A fix for a fall-through hazard lands on the node that failed, leaving the same hazard in every node upstream of it"
type: learning
timestamp: "2026-09-18T21:35:00Z"
source: ISSUE-3399
signal: theme-candidate
---

A review found that a refusal arm in a py_trees `Selector` fell through to the
permissive arm whenever the refusal's *emit* failed: `_EmitSingleActivityBase`
converts any exception into FAILURE, and a Selector reads FAILURE as "try the
next child". A declining admission policy therefore produced a full accept.

The fix was to persist the decision before the emit and gate the permissive arm
on that record's absence. It closed the reported failure completely. A second,
adversarial review then broke it again — in the *same arm*, one node earlier:

```text
DeclineProposalArm (Sequence)
  ├─ Inverter(already-answered?)   ← still fell through
  ├─ Inverter(evaluate)            ← still fell through
  ├─ RecordDecline                 ← barrier installed here
  └─ EmitReject                    ← the reported failure
```

The arm had four children. The first fix moved the barrier from child 4 to child
3 and stopped there, because child 4 was the one named in the finding. Children
1–2 were never asked the question. Making child 1's store read raise reproduced
the original symptom exactly: declining policy, status SUCCESS, case created,
`Accept` queued — and the admission backend never even consulted.

**The claim.** When a defect is "control reached the wrong branch", the report
names *one* node, but the defect belongs to the *edge* — every node on the path
shares it. Fixing the named node is a local repair of a positional bug. The
question that finds the rest is not "why did this node fail?" but **"for every
node between the entry to this branch and the point of no return, what happens if
it fails?"** In a Selector arm the answer is uniform and usually wrong: FAILURE
means the sibling runs.

A sharpening that fell out of it: in a *refusal* arm no status is safe. FAILURE
runs the permissive sibling; SUCCESS skips the refusal and runs it too. So the
usual convention that `update()` catches and returns FAILURE (BT-HELPER-01) is
actively unsafe there, and the node that tried hardest to be careful — the only
one with a `try/except` — was the only unsafe one. Letting the exception reach
the bridge was the correct handling. This is written up as durable guidance in
`notes/bt-pitfalls.md` § "A Refusal Arm in a Selector Fails Toward 'Admit'"; the
generalisation above is what this entry is watching.

A second observation from the same session, worth recording because it is cheap
to act on: every error-direction claim in the new nodes' docstrings was prose
nothing could check, and one of them was flatly false — it asserted that
returning SUCCESS on a store error "blocks adjudication", when in a Selector it
skips the refusal arm and admits. The fix was a regression test per claimed
direction, after which the claims are ratchetable. This is a second witness for
[[20260918-3337-a-doc-rots-first-in-the-column-no-test-can-hold]]'s generalised
form — "could a test fail on this sentence?" — applied to a docstring rather than
a table, and in a doc written the same day as the code it described. Staleness was
not the mechanism; unverifiability alone was.

**How to apply.** After fixing a wrong-branch defect, enumerate the nodes on the
path rather than re-reading the one that failed. For each, ask what its failure
does to control flow, and write a test per answer. If the answers are not
uniform, say which is which at the site — and if a node's safe behaviour is "let
the exception out", say that too, because it looks like an omission to the next
reader and will be "fixed" into a `try/except`.

Corroboration needed: one session, though it is a two-witness instance in
miniature — the same hazard found twice, at two positions, by two reviewers. A
second witness would be any session where a fall-through, off-by-one, or
ordering fix is reported at one site and the same defect survives at an adjacent
one. A negative witness would be a positional defect that genuinely was confined
to the node named in the report.

Related: [[20260918-3399-bt18-has-no-contract-for-a-refusal-carrying-a-payload]]
is the spec-level half of the same work.
[[20260916-3192-tightening-a-resolver-wakes-dormant-checks]] shares a family
resemblance — a permissive path silently load-bearing — but its mechanism is a
guard consuming an empty answer, not a branch consuming a status.
