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
"""The Invite a case owner's embargo decision names in ``inReplyTo`` (ADR-0180).

The owner's ``Add`` and ``Reject(EmbargoEvent)[target=VulnerabilityCase]``
name the ``Invite(EmbargoEvent)`` that proposed the embargo.  The owner's
trigger reads it from its own store's open-proposal record
(``pending_embargo_proposal_index``); a test that builds the decision
through the trigger-activity adapter reads it the same way.
"""

import json
from typing import Any, cast

from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.wire.as2.factories import (
    activate_embargo_activity,
    reject_embargo_proposal_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Add,
    as_Reject,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent


def held_proposal_id(
    store: CasePersistence, case_id: str, embargo_id: str
) -> str:
    """The Invite *store*'s case records as proposing *embargo_id*.

    Raises:
        AssertionError: the store holds no case *case_id*, or its case
            records no open proposal for *embargo_id*.
    """
    case = store.read_case(case_id)
    assert case is not None, f"store holds no case {case_id}"
    proposal_id = case.pending_embargo_proposal_index.get(embargo_id)
    assert proposal_id is not None, (
        f"case {case_id} records no open proposal for embargo {embargo_id}"
    )
    return str(proposal_id)


#: The ``inReplyTo`` of an owner decision a test builds on a register it
#: seeded directly, so no ``Invite(EmbargoEvent)`` was ever sent.  No
#: receiver reads the decision's ``inReplyTo``: it decides on the embargo
#: its object names (MSM-07-008, MSM-07-009), so the value only has to be
#: present (RF-08-003).
SEEDED_PROPOSAL_ID = "https://example.org/embargo_proposals/seeded"


def seeded_activation(embargo: as_EmbargoEvent, **kwargs: Any) -> as_Add:
    """:func:`activate_embargo_activity` naming :data:`SEEDED_PROPOSAL_ID`."""
    return activate_embargo_activity(
        embargo, in_reply_to=SEEDED_PROPOSAL_ID, **kwargs
    )


def seeded_proposal_rejection(
    embargo: as_EmbargoEvent, **kwargs: Any
) -> as_Reject:
    """:func:`reject_embargo_proposal_activity` naming :data:`SEEDED_PROPOSAL_ID`."""
    return reject_embargo_proposal_activity(
        embargo, in_reply_to=SEEDED_PROPOSAL_ID, **kwargs
    )


def decided_proposal_id(case_id: str) -> str:
    """An Invite id the owner's store does not record as an open proposal.

    The ``inReplyTo`` a test gives an owner decision on an embargo that is
    no open proposal, such as the embargo already in force, which the
    CASE_MANAGER refuses (MSM-07-029).
    """
    return f"{case_id}/embargo_proposals/decided"


def owner_decision_body(
    owner_store: CaseOutboxPersistence,
    case_id: str,
    embargo_id: str,
    *,
    owner: str,
    manager: str,
    accept: bool,
    proposal_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """The owner's decision on *embargo_id*, built by its trigger adapter.

    ``Add`` when *accept*, else ``Reject(EmbargoEvent)``, addressed to
    *manager*.  ``inReplyTo`` names *proposal_id*, by default the Invite
    *owner_store* records for the open proposal (:func:`held_proposal_id`,
    ADR-0180).  Returns the decision's id and its sealed body.
    """
    adapter = TriggerActivityAdapter(owner_store)
    build = (
        adapter.activate_embargo if accept else adapter.reject_embargo_proposal
    )
    activity_id, sealed = build(
        embargo_id=embargo_id,
        proposal_id=proposal_id
        or held_proposal_id(owner_store, case_id, embargo_id),
        case_id=case_id,
        actor=owner,
        to=[manager],
    )
    return activity_id, cast(dict[str, Any], json.loads(sealed))
