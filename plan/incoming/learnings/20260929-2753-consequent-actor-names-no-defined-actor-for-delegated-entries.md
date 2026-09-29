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
test compares to anything.

Resolution: PR #3881 settled the semantics by the rule the wire format already
had (CM-24-001/002, PCR-08-007) — the label is the entry's recorded `actor`, the
literal emitter, so every `invite_actor_to_case` edge is `case-actor` and the
requesting participant lives in `attributedTo` — amended DEMOMA-22-004 to say so,
and relabelled the ten invite edges. Making the label load-bearing in
`check_causal_edges` remains Concern #3882; PR #3881 adds only a shape-local
check (an invitation response is never attributed to its inviter).
