---
title: No spec entry requires message-subject identities to come from the message
type: learning
timestamp: 2026-09-01
source: ISSUE-2762
signal: spec-gap
---

CLP-10-005 through CLP-10-008 pin down one half of the ADR-0022 contract: a
received-side `execute()` builds one tree and runs it once under
`actor_id=resolve_receiving_actor_id(...)`. Nothing in the spec corpus states
the complementary half — that every **subject** identity the message names
(invitee, accepting actor, rejecting actor, target actor) MUST be read from the
message rather than inferred from the receiving actor.

ADR-0022 says it only in prose, under Decision Drivers: "Per-message asserter
identities that differ from `receiving_actor_id` (e.g. `invitee_id`,
`accepting_actor_id`) are legitimate inputs to leaf nodes — they are not
legitimate values for the `actor_id` argument."

That gap is what let #2762 in. The fix for #2446 correctly replaced a
silent-drop early return with `resolve_receiving_actor_id()`, then reused the
resolved value for `invitee_id` — satisfying every written requirement while
inverting the semantics. The same gap independently produced a second defect in
`reject_invite_to_embargo_tree`, which accepted a `rejecting_actor_id` and only
logged it.

This is protocol-visible, not agent guidance: it determines *which participant's
consent state changes* and *whose RSVP deadline is recorded* (CM-28-001,
CM-28-003). A candidate CLP-10-009 would state it as a MUST with ADR-0022 as
its `adr:` reference, and could be verified structurally — a received-side use
case that passes the result of `resolve_receiving_actor_id()` as anything other
than `execute_with_setup(actor_id=...)` is a violation. Note the coverage
ratchet: a new `kind: protocol` entry needs a test carrying
`@pytest.mark.spec("CLP-10-009")`; the tests added in
`test/core/use_cases/received/test_embargo_invite_lapse.py`
(`TestInviteeIsTheAddressee`) would serve.

Interim guidance landed in `vultron/core/AGENTS.md` § "A Message Subject Is
Never `resolve_receiving_actor_id()`".
