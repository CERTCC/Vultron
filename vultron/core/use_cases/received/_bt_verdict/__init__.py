#!/usr/bin/env python

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

"""Turn a received-side BT run into the handler's ``HandlerResult`` (#2255).

A tree's root status says only whether it succeeded. A handler has to report
more than that (HP-01-003, ADR-0095): a benign no-op is ``SKIPPED``, a refused
assertion is ``REFUSED``, and a programming error is neither — it propagates.

:func:`verdict_from_bt` applies the default reading of a finished run:

- ``SUCCESS`` → ``APPLIED``.
- A leadership skip (the tree never ran) → ``SKIPPED``.
- ``internal_error``, or a node missing its DataLayer or a port → raise
  :class:`~vultron.errors.VultronBTInternalError`.
- The post-close guard refused (CM-23-013) → ``REFUSED``, ahead of any other
  reading of the failure.
- Any other ``FAILURE`` → ``REFUSED``, with the failing leaf's reason.

:func:`applied_or_raise` is the variant for a tree that only stores or commits:
there any ``FAILURE`` raises.

Handlers refine it where the tree says more: a guard whose ``FAILURE`` is a
duplicate, a role gate that skips as ``SUCCESS`` because this actor is not the
case's CASE_MANAGER. They ask with :func:`node_failed` /
:func:`node_succeeded`, which look a node up by type the way
``_filter_node_wholly_refused`` in ``status.py`` does, because a node's
``feedback_message`` usually embeds ids and is not a stable key.

A role-gate skip is not a benign no-op. The message was the CASE_MANAGER's to
act on and reached an actor that is not it, so the handler reports ``REFUSED``
(HP-01-005) through :func:`not_case_manager_refusal`; ``SKIPPED`` is reserved
for a duplicate or an otherwise idempotent re-delivery.

A tree that declares its paths needs no such reading: its path door stage
refuses the undeclared path itself, :func:`door_refusal` returns that refusal
with the reason the stage composed from the resolved path and the declaration
(HP-01-039), and the handler asks :func:`received_path` which of the three
paths it is on.

:func:`not_case_manager` and :func:`not_case_manager_refusal` remain for the
trees still to be migrated, and go with the last of them rather than with a
migration wave of their own: the predicate reads a failed
``CheckIsCaseManagerNode`` anywhere in the tree, and the factory's own gate
round ``manager_effects`` holds one in every tree that has any, so the
predicate cannot be deleted while a tree that passes no path declaration
still reaches it.  The note and dead-letter trees (#5785) and the
``Offer(VulnerabilityReport)`` trees (#5046) are the ones left.
"""

from vultron.core.use_cases.received._bt_verdict.case_manager import (
    case_manager_absence_refusal,
    case_manager_verdict,
    not_case_manager,
    not_case_manager_refusal,
    reference_edit_verdict,
    unheld_case_refusal,
)
from vultron.core.use_cases.received._bt_verdict.door import (
    addressee_refusal,
    closed_sender_verdict,
    door_refusal,
    guard_refusal,
    incomplete_activity_refusal,
    path_refusal,
    post_close_refusal,
)
from vultron.core.use_cases.received._bt_verdict.redelivery import (
    add_note_redelivery_verdict,
    embargo_answer_repeat_verdict,
    embargo_withdrawal_redelivery_verdict,
    ownership_answer_verdict,
    ownership_offer_verdict,
    pxa_refusal_verdict,
    rm_declaration_verdict,
    role_offer_answer_verdict,
    role_offer_verdict,
    stale_case_copy_verdict,
)
from vultron.core.use_cases.received._bt_verdict.tree_lookup import (
    door_guards_admitted,
    failure_reason,
    find_named,
    find_node,
    named_node_status,
    node_failed,
    node_succeeded,
    received_path,
    taken_diversion,
)
from vultron.core.use_cases.received._bt_verdict.verdict import (
    applied_or_raise,
    intake_verdict,
    verdict_from_bt,
)

__all__ = [
    "add_note_redelivery_verdict",
    "addressee_refusal",
    "applied_or_raise",
    "case_manager_absence_refusal",
    "case_manager_verdict",
    "closed_sender_verdict",
    "door_guards_admitted",
    "door_refusal",
    "embargo_answer_repeat_verdict",
    "embargo_withdrawal_redelivery_verdict",
    "failure_reason",
    "find_named",
    "find_node",
    "guard_refusal",
    "incomplete_activity_refusal",
    "intake_verdict",
    "named_node_status",
    "node_failed",
    "node_succeeded",
    "not_case_manager",
    "not_case_manager_refusal",
    "ownership_answer_verdict",
    "ownership_offer_verdict",
    "path_refusal",
    "post_close_refusal",
    "pxa_refusal_verdict",
    "received_path",
    "reference_edit_verdict",
    "rm_declaration_verdict",
    "role_offer_answer_verdict",
    "role_offer_verdict",
    "stale_case_copy_verdict",
    "taken_diversion",
    "unheld_case_refusal",
    "verdict_from_bt",
]
