---
title: Ask expiry timing is stated for one register and silent for the other
type: learning
timestamp: 2026-11-02T00:00:00+00:00
source: ISSUE-5591
signal: spec-ambiguity
---

ASK-05-001 is a MUST: "A gated interaction tree MUST treat an outstanding ask
past its deadline as expired at the next entry into the tree, without requiring
a prior reaping pass." Read alone, it forbids moving expiry off the lookup
path — which is what #5591 had to do to make a demo recording reproducible,
because under the recording clock a lookup that reads the clock moves every
later timestamp.

The two are reconcilable: ASK-05-001 governs the **outstanding-ask register** of
ASK-04, which MUST be durable across restarts (ASK-04-003), while the
pending-assertion store is explicitly ephemeral and is a *separate*
instantiation of the shared lifecycle ASK-04-007 calls for. So ASK-05-001 does
not bind the pending-assertion store, and SYNC-11-005 — the store's own timeout
requirement — says only that an entry past its window "SHOULD be marked
timed-out and SHOULD no longer suppress future re-emits", never where that mark
is applied.

Three things make this hard to see, and a future agent changing either register
will hit them again:

1. Nothing in SYNC-11 says it is *not* the register ASK-05 governs, and nothing
   in ASK-05 says it is *not* the store SYNC-11 describes. The only link is
   ASK-04-007's "instantiated separately for each use", two groups away.
2. `record_pending_assertion()`'s docstring cites ASK-04-008 — a register
   requirement — which reads as the store being the ASK-04 register.
3. ASK-05-001's "at the next entry into the tree" is the one place in the corpus
   that says *when* an expiry is evaluated. Once the shared register of
   ASK-04-007 exists, that timing and "no read path may read the recording
   clock" have to be satisfied together, and no requirement says how.

Open question for the corpus: does ASK-05-001's timing survive the clock-free
read rule, and if so, where does the deciding instant come from — the entry into
the tree being a write boundary, or a reap pass (ASK-05-002, #2887) being the
only evaluator? The same question is what #5649 and #5650 each have to answer
for their own call sites.
