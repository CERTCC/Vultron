#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""The case-invite chain shared by every multi-actor demo scenario.

A participant joins a case through one chain: the CASE_MANAGER emits a case
Invite (CM-17-007, ADR-0109), the invitee's DataLayer receives it, the invitee
answers it, and — on an accept — the trust-bootstrap
``Announce(VulnerabilityCase)`` seeds the invitee's case replica
(MV-10-003/MV-10-004).  The CASE_MANAGER then sends the full-case Invite, and
every invitee, whatever its role, judges the case by replying to it
(CM-11-010, CM-11-011): the chain asserts the whole sequence — stub Invite,
stub Accept, Announce and replay, full-case Invite, reply.
Every scenario once wrote that chain out by hand (DEMOMA-17-001, #4192); this
module is the one place that owns it, with the variants as parameters:

- **who asks** — an inviting participant triggers the invite
  (``inviter=CaseInviter(...)``), or the CaseActor already invited after the
  owner approved a recommendation (``inviter=None``, ADR-0026);
- **how the invitee answers** — ``respond="accept"`` or ``"reject"``;
- **whether the Invite's sender is checked** — ``expect_emitted_by``;
- **what follows** — ``then`` runs inside the gate, so it is skipped when any
  earlier link fails (ADR-0058, EDF-06-005, #3038).

A composed story needs the chain in **two halves**, because the invitee's
decision is a branch point that falls between the Invite and the answer:
:func:`invite_and_await_delivery` then :func:`answer_case_invite`, with the
story's ``choose(...)`` between them (``notes/demo-scenario-tree.md``
§ "Composition").  Both halves and the whole chain share one copy of each
link, so the two forms cannot drift, and they use the same step and gate
labels.

The chain reports pass/fail through ``demo_step`` / ``demo_gate`` /
``demo_check`` as the hand-written copies did: a failed trigger or lookup
skips its dependents and is recorded, never raised.  Two differences: step
and gate labels are now uniform across scenarios, and the Accept result is no
longer re-validated as a transitive activity (it fed only a log line).  A
failure inside ``then`` is recorded against the delivery gate, whose label
names the invite rather than the cause.

The package is split by concern (CS-18-005): :mod:`.links` holds the
chain's parameters and each of its links, and :mod:`.chain` the whole chain
and its two halves.  Every public name is re-exported here (CS-18-003).
"""

from vultron.demo.helpers.invite_chain.chain import (
    answer_case_invite,
    invite_and_await_delivery,
    run_case_invite_chain,
)
from vultron.demo.helpers.invite_chain.links import (
    DEMO_STUB_SUMMARY,
    FULL_CASE_REPLY_TIMEOUT,
    CaseInviter,
    EmittedBy,
    reply_to_full_case_invite,
)

__all__ = [
    "DEMO_STUB_SUMMARY",
    "FULL_CASE_REPLY_TIMEOUT",
    "CaseInviter",
    "EmittedBy",
    "answer_case_invite",
    "invite_and_await_delivery",
    "reply_to_full_case_invite",
    "run_case_invite_chain",
]
