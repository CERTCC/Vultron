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

"""The drained scenarios that send again today, pinned per semantic (#5047).

When the outbox is delivered between runs, as the inbox's drain after every
delivery does, a later run of some scenarios sends again.  Part 3 of #5047
fixes them.  Each entry is a strict ``xfail``: when part 3 fixes one, its
pass fails the run and the entry must go.  A scenario that already passes
drained is not listed.

Keyed by (path, kind, semantic): path ``rerun`` (a re-run from holding) or
``replay`` (a re-run, a hold for its retry, then the replay); kind
``applied`` or ``refused``.  The value names the classes it shows:

- **A**: the replay answers the activity's stale ``ledgerPosition`` again,
  replaying entries the sender already received, its own act's and any
  refusal note's among them, as new ``Announce(CaseLedgerEntry)`` under
  minted ids;
- **B**: the replay of a refused activity sends its refusal notice again,
  under the same derived id;
- **C**: a re-run's effects emit their derived-id activity again, and its
  entry, already committed, is announced again under minted ids.
"""

from vultron.core.models.events.base import MessageSemantics

CLASSES: dict[str, str] = {
    "A": "a replay answers the stale ledgerPosition again",
    "B": "a replay answers the refusal again",
    "C": "a re-run's effects emit and announce again",
}

DRAINED_FAILURES: dict[tuple[str, str, MessageSemantics], str] = {
    (
        "replay",
        "applied",
        MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER,
    ): "A",
    ("replay", "applied", MessageSemantics.ACCEPT_CASE_PARTICIPANT_ROLE): "A",
    (
        "replay",
        "applied",
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_FULL_CASE,
    ): "A",
    (
        "replay",
        "applied",
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
    ): "A",
    (
        "replay",
        "applied",
        MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT,
    ): "A, C",
    ("replay", "applied", MessageSemantics.ACTIVATE_EMBARGO_ON_CASE): "A",
    ("replay", "applied", MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE): "A",
    ("replay", "applied", MessageSemantics.ADD_NOTE_TO_CASE): "A",
    (
        "replay",
        "applied",
        MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
    ): "A",
    ("replay", "applied", MessageSemantics.ADD_REPORT_TO_CASE): "A",
    ("replay", "applied", MessageSemantics.CREATE_CASE_PROPOSAL): "C",
    ("replay", "applied", MessageSemantics.DEFER_CASE): "A",
    ("replay", "applied", MessageSemantics.ENGAGE_CASE): "A",
    ("replay", "applied", MessageSemantics.OFFER_ACTOR_TO_CASE): "A, C",
    ("replay", "applied", MessageSemantics.OFFER_CASE_PARTICIPANT_ROLE): "A",
    (
        "replay",
        "applied",
        MessageSemantics.PROPOSE_CASE_OWNERSHIP_TRANSFER,
    ): "A",
    (
        "replay",
        "applied",
        MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER,
    ): "A",
    ("replay", "applied", MessageSemantics.REJECT_CASE_PARTICIPANT_ROLE): "A",
    (
        "replay",
        "applied",
        MessageSemantics.REJECT_EMBARGO_PROPOSAL_ON_CASE,
    ): "A",
    (
        "replay",
        "applied",
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
    ): "A",
    (
        "replay",
        "applied",
        MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT,
    ): "A, C",
    (
        "replay",
        "applied",
        MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE,
    ): "A",
    (
        "replay",
        "applied",
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE,
    ): "A",
    ("replay", "applied", MessageSemantics.REMOVE_NOTE_FROM_CASE): "A",
    (
        "replay",
        "applied",
        MessageSemantics.TENTATIVE_REJECT_INVITE_ACTOR_TO_FULL_CASE,
    ): "A",
    ("replay", "applied", MessageSemantics.UNDO_CASE_OWNERSHIP_TRANSFER): "A",
    (
        "replay",
        "refused",
        MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER,
    ): "A, B",
    ("replay", "refused", MessageSemantics.ACCEPT_CASE_PARTICIPANT_ROLE): "B",
    ("replay", "refused", MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE): "B",
    (
        "replay",
        "refused",
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_FULL_CASE,
    ): "A, B",
    (
        "replay",
        "refused",
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
    ): "A, B",
    ("replay", "refused", MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT): "B",
    ("replay", "refused", MessageSemantics.ACTIVATE_EMBARGO_ON_CASE): "B",
    ("replay", "refused", MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE): "B",
    ("replay", "refused", MessageSemantics.ADD_NOTE_TO_CASE): "A, B",
    (
        "replay",
        "refused",
        MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
    ): "A, B",
    ("replay", "refused", MessageSemantics.INVALIDATE_REPORT): "B",
    ("replay", "refused", MessageSemantics.INVITE_TO_EMBARGO_ON_CASE): "B",
    ("replay", "refused", MessageSemantics.OFFER_ACTOR_TO_CASE): "B",
    ("replay", "refused", MessageSemantics.OFFER_CASE_PARTICIPANT_ROLE): "B",
    (
        "replay",
        "refused",
        MessageSemantics.PROPOSE_CASE_OWNERSHIP_TRANSFER,
    ): "A, B",
    (
        "replay",
        "refused",
        MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER,
    ): "A, B",
    ("replay", "refused", MessageSemantics.REJECT_CASE_PARTICIPANT_ROLE): "B",
    (
        "replay",
        "refused",
        MessageSemantics.REJECT_EMBARGO_PROPOSAL_ON_CASE,
    ): "B",
    (
        "replay",
        "refused",
        MessageSemantics.REJECT_INVITE_ACTOR_TO_FULL_CASE,
    ): "A, B",
    (
        "replay",
        "refused",
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
    ): "A, B",
    ("replay", "refused", MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT): "B",
    (
        "replay",
        "refused",
        MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE,
    ): "B",
    (
        "replay",
        "refused",
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE,
    ): "B",
    (
        "replay",
        "refused",
        MessageSemantics.TENTATIVE_REJECT_INVITE_ACTOR_TO_FULL_CASE,
    ): "A, B",
    (
        "replay",
        "refused",
        MessageSemantics.UNDO_CASE_OWNERSHIP_TRANSFER,
    ): "A, B",
    ("replay", "refused", MessageSemantics.VALIDATE_REPORT): "B",
    ("replay", "refused", MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE): "B",
    ("rerun", "applied", MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT): "C",
    ("rerun", "applied", MessageSemantics.CREATE_CASE_PROPOSAL): "C",
    ("rerun", "applied", MessageSemantics.OFFER_ACTOR_TO_CASE): "C",
    ("rerun", "applied", MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT): "C",
}

__all__ = ["CLASSES", "DRAINED_FAILURES"]
