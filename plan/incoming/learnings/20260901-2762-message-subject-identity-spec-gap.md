---
title: No spec entry requires message-subject identities to come from the message
type: learning
timestamp: "2026-09-01T00:00:00Z"
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
CM-28-003). A new CLP-10 entry — **at the next free ID in the group, not 009,
which is already taken by the rejection-validator placement rule from
ISSUE-2254** — would state it as a MUST with ADR-0022 as its `adr:` reference,
and could be verified structurally: a received-side use case that passes the
result of `resolve_receiving_actor_id()` as anything other than
`execute_with_setup(actor_id=...)` is a violation. Note the coverage ratchet: a
new `kind: protocol` entry needs a test carrying the matching
`@pytest.mark.spec(...)` marker; the tests added in
`test/core/use_cases/received/test_embargo_invite_lapse.py`
(`TestInviteeIsTheAddressee`, `TestInviteeIdProperty`) would serve.

A second requirement is worth stating alongside it: subject resolution MUST be
by **addressee membership**, not by position in `to:`. Taking `to[0]`
positionally is correct only for the first recipient of a multi-party activity
and silently wrong for every other one. `_is_primary_submit_report_recipient()`
in `received/report.py` had the membership pattern already; the embargo path
did not reuse it.

Interim guidance landed in `vultron/core/AGENTS.md` § "A Message Subject Is
Never `resolve_receiving_actor_id()`".

---

**Promoted**: 2026-09-03 — captured in `specs/case-ledger-processing.yaml` (new CLP-10-015 and CLP-10-016: message-subject identities MUST be read from the received activity by addressee membership, not from `resolve_receiving_actor_id()`). Docs PR: <DOCS_PR_URL>.
