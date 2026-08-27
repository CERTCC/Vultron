---
title: Actor discovery seam sits at use-case level, not as a BT node
type: learning
timestamp: 2026-08-26T15:15:00Z
source: ISSUE-2469
signal: design-question
---

Issue #2469 listed "Where does the node sit — is discovery a BT concern at all,
or an adapter one consulted before the BT runs?" as an open design question.

**Decision made in PR #2641**: the seam stays at the `_prepare()` / use-case
constructor level (not as a BT node). `SvcInviteActorToCaseUseCase`,
`SvcSuggestActorToCaseUseCase`, and `SvcOfferCaseOwnershipTransferUseCase`
each accept a `call_out: ActorDiscoveryCallOutBundle` parameter and pass it
to `_record_named_peer`.

**Rationale**: Creating a `CoreActor` record does not affect protocol-observable
state (no activity emitted, no RM/EM/CS transition). BT-15-001 ("any action
that affects protocol-observable state MUST be in a BT node") therefore does
not apply. Keeping the seam in `_prepare()` avoids the complexity of calling
a BT node procedurally from outside a tick context and matches how
`_record_named_peer` currently works.

**Future work**: if a real directory service requires async semantics or
needs to interact with the BT blackboard (e.g., to write resolved actor data
for downstream nodes to read), the seam should be promoted to a proper BT
subtree at that point. The bundle infrastructure (ADR-0025 factory) is already
in place to support this without changing call sites.

**Promoted**: 2026-08-27 — archived (already in specs/notes/AGENTS.md or tracked as GitHub issue). Docs PR: <pending>.
