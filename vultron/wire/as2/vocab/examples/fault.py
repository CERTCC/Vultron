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
"""Example ``Create(ProcessingFault)``: a message received but not understood."""

from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_STATUS_ASSERTION_REFUSED_IMPOSSIBLE_STATE,
)
from vultron.wire.as2.factories.fault import (
    create_processing_fault_activity,
    refusal_notice_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
    as_Reject,
)
from vultron.wire.as2.vocab.examples._base import _CASE_ACTOR, vendor
from vultron.wire.as2.vocab.examples.status import (
    add_fix_readiness_to_participant,
)
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault


def create_processing_fault() -> as_Create:
    """A Vendor's replica refuses a ledger entry naming an impossible state.

    The Vendor cannot apply the ``Announce(CaseLedgerEntry)`` the Case
    Manager sent, because the participant status it records violates the
    composite-state entailments, so it reports the fault to the Case Manager
    (RSH-09-006).  The fault points at the failed activity by ``inReplyTo``
    and names its failure class by URI, with no implementation diagnostics
    (ASK-07-003, ASK-07-004, ASK-07-006).
    """
    fault = as_ProcessingFault(
        failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED_IMPOSSIBLE_STATE,
        in_reply_to=f"{_CASE_ACTOR.id_}/announce/9",
    )
    return create_processing_fault_activity(
        actor=vendor().id_,
        fault=fault,
        to=[_CASE_ACTOR.id_],
    )


def refusal_notice() -> as_Reject:
    """The Case Manager refuses a Vendor's status assertion a guard rejected.

    The refused ``Add(ParticipantStatus)`` is carried inline, ``inReplyTo``
    names it, and ``summary`` gives the guard's reason (CLP-05-001).  Nothing
    is ledgered for the refusal (CLP-05-002).
    """
    refused = add_fix_readiness_to_participant()
    assert isinstance(refused.actor, str)
    return refusal_notice_activity(
        refused.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            serialize_as_any=True,
        ),
        "fix readiness (VF) asserted before vendor awareness (Vf) was"
        " recorded for the Vendor",
        actor=_CASE_ACTOR.id_,
        to=[refused.actor],
        context="https://vultron.example/cases/1",
    )
