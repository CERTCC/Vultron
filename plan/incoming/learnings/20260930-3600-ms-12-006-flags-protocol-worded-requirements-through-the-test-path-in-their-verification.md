---
title: "MS-12-006's 'references a file path' question is answered by the verification clause, not the requirement — 207 of 212 hits were protocol-worded statements whose only code reference was the `test/` path MS-10-003 obliges them to carry"
type: learning
timestamp: "2026-09-30T14:30:00Z"
source: ISSUE-3600
signal: spec-ambiguity
---

MS-12-006 scans `statement` **or** `verification` for a codebase construct on a
story-less `kind: protocol` spec. Against the live corpus the detector flagged
212 specs. Only 5 named code in their `statement`; the other 207 matched solely
because their `verification:` clause names a `test/…` or `vultron/…` path — and
it names one because MS-10-003 requires every MUST to carry a `verification:`
and MS-15-001 requires the path it names to resolve. The corpus convention for
"verifiable" is "names the test that checks it", so for a story-less protocol
spec MS-12-002's question ("does the spec reference a file path?") is answered
by an obligation the corpus imposed, not by anything the requirement itself
says.

The issue anticipated the shape (it measured 666 of 1320 protocol specs with
the unqualified wording and chose the stories gate rather than a statement-only
scan), and `notes/spec-authoring-rules.md` records the gate as confining the
check to "the population where a codebase reference actually indicates
misclassification". What neither quantified is how much of the remaining
population is protocol-worded. Reading the 212, roughly 90 are wire or
state-machine obligations an independent implementer would have to satisfy —
`CSB-12-002` ("A Participant entering CS Public Aware MUST NOT seek new
embargoes"), `CLP-14-010` (gapless `log_index`), `SYNC-03-003` (idempotent
replication), `RF-02-002` (`Accept` carries `object`), `MV-03-002` (blank
required field is absent), the `IE` inbox status codes — and they now sit on
the `project` page because their verification names the test that proves them.

The relabel was applied as specified: the decision tree is mechanical by
design (ADR-0038), the issue said "do not widen this while implementing", and
the alternative — rewriting ~200 verification clauses to avoid naming a path —
would game the detector rather than answer it. But the ambiguity is real and
sits in MS-12-002/MS-12-006: whether a `verification:` clause's path counts as
"the spec referencing a file path" is a decision the spec never states. Two
readings are coherent:

- **Yes** (current): a protocol spec must be verifiable without naming this
  codebase, so a protocol `verification:` should read like a conformance test,
  not a pytest path. Then MS-10-003's convention needs a protocol-tier variant.
- **No**: MS-12-006 should scan `statement` only for the protocol population,
  and the 207 return to `protocol` with their suppressions — which is the
  wrong-way ratchet the issue set out to stop, unless stories arrive first.

Either way, issue #3601 and the stories epic (#2717) should look first at the
~90 protocol-worded specs relabeled here: mapping them to stories restores
`protocol` under both readings. The decision and the re-adjudication are
tracked as Concern #3943, which carries the list.
