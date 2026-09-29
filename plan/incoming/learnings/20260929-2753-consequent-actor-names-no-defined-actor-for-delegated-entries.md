---
title: "DEMOMA-22-004's \"actor that commits the consequent\" names no one the ledger can identify — the CASE_MANAGER commits every entry, and for a delegated emission the narratives split between the payload actor and the delegating actor"
type: learning
timestamp: "2026-09-29T18:10:00Z"
source: ISSUE-2753
signal: spec-ambiguity
---

While fixing the `consequent_actor` label on the fcv-reject rejection edge
(#2753), the question "which actor is the right one?" had no spec answer.
DEMOMA-22-004 says each edge names "the actor that commits the consequent", but
under CLP-09 the CASE_MANAGER commits every canonical entry, so read literally
every label would be `case-actor`.

The narratives instead follow an unstated convention: the participant whose act
the entry records (`payloadSnapshot.actor`), with `case-actor` reserved for
entries the Case Actor originates itself. That convention breaks on delegated
emissions. The Vendor2 invite in fvcv-handoff is emitted as the CaseActor with
the Coordinator as `attributedTo` (the demo asserts this, PCR-08-008), and the
narratives disagree on how to label it: `fvcv-handoff.md` and
`fccv-handoff.md` say the delegating actor, `fccv-extension.md` and
`fvcv-extension.md` say `case-actor`.

Nothing surfaced the split because `check_causal_edges` reads the label only for
its failure message (`notes/demo-ci-invariants.md` calls it "documentary"), so
the field DEMOMA-22-004 makes mandatory is the one field of the edge that no
test compares to anything. The ambiguity and the enforcement gap are tracked
together in Concern #3882, filed from PR #3881; PR #3881 itself adds only a
shape-local check (an invitation response is never attributed to its inviter).
