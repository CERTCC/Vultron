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

from typing import Any

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
