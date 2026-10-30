---
title: "No requirement says the DataLayer inspection routes serve every stored row by its key"
type: learning
timestamp: "2026-10-30T18:30:00Z"
source: ISSUE-5529
signal: spec-gap
---

**Trigger.** You are fixing or adding a read route under
`vultron/adapters/driving/fastapi/routers/datalayer.py`, and you look for the
requirement your change has to satisfy.

**Claim.** The spec corpus says how a datalayer read must *render* what it
serves — ARCH-20-006 (only an AS2 class is dumped as an AS2 document),
HTTP-09-001 and HTTP-09-002 (the wire class is the response model; return an
`AS2JSONResponse`) — and nothing about *what* it must reach. There is no
requirement that a row the store holds is readable by its key, that two reads
of the same row agree, or that a read mints no id and reads no clock. Those
three rules are each real, each now carries a test, and each was derived from
an issue body rather than from a requirement.

**Evidence.** Issue #5529 carried no `Governing specs:` line, so the Spec
manifest for PR #5548 had to record "issue #5529 names none"; its own
"Expected" section states the rule ("every stored record can be read by its
key") as a fresh judgment. #5510 established "a GET serves the stored object
and mints nothing" the same way, and #5540 and #5547 are the two reads of one
row disagreeing — one unstated contract behind each.

**Confirmed once already.** The review of PR #5548 filed #5551, which asks
what a read route's type segment means and has to argue the answer from first
principles too, and whose recommended resolution is to write the rule into the
route description because no requirement holds it.

**How to apply it.** `learn` decides whether the inspection surface earns spec
entries (an `HTTP-` group beside HTTP-09, or a `DL-` group, since the rules are
about the store's read surface rather than the wire rendering), or whether it
is deliberately unspecified prototype scaffolding — in which case say so in one
place, so the next agent stops looking. The candidate statements are: a read
serves every row the store holds, under the key the store holds it by; every
read of one row answers the same body; and a read mints no id and reads no
clock.
