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
"""
Factory functions for outbound Vultron case-management activities.

These are the sole public construction API for activities involving
``as_VulnerabilityCase`` objects. Internal activity subclasses are
imported in the submodules, grouped by concern, and MUST NOT be imported by
callers.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

from vultron.wire.as2.factories.case.content import (
    add_case_reference_to_case_activity,
    add_note_to_case_activity,
    add_report_to_case_activity,
    add_status_to_case_activity,
    add_vulnerability_item_to_case_activity,
    announce_vulnerability_case_activity,
    create_case_activity,
    update_case_activity,
)
from vultron.wire.as2.factories.case.full_case_invite import (
    rm_accept_full_case_invite_activity,
    rm_invite_to_full_case_activity,
    rm_reject_full_case_invite_activity,
    rm_tentative_reject_full_case_invite_activity,
)
from vultron.wire.as2.factories.case.invite import (
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
    rm_reject_invite_to_case_activity,
)
from vultron.wire.as2.factories.case.ownership import (
    accept_case_ownership_transfer_activity,
    offer_case_ownership_transfer_activity,
    propose_case_ownership_transfer_activity,
    reject_case_ownership_transfer_activity,
    undo_case_ownership_transfer_activity,
)
from vultron.wire.as2.factories.case.proposal import (
    accept_case_proposal_activity,
    create_case_proposal_activity,
    reject_case_proposal_activity,
)
from vultron.wire.as2.factories.case.rm import (
    reject_close_case_activity,
    rm_close_case_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
)
from vultron.wire.as2.factories.case.roles import (
    accept_case_participant_role_activity,
    offer_case_participant_role_activity,
    reject_case_participant_role_activity,
)

__all__ = [
    "accept_case_ownership_transfer_activity",
    "accept_case_participant_role_activity",
    "accept_case_proposal_activity",
    "add_case_reference_to_case_activity",
    "add_note_to_case_activity",
    "add_vulnerability_item_to_case_activity",
    "add_report_to_case_activity",
    "add_status_to_case_activity",
    "announce_vulnerability_case_activity",
    "create_case_activity",
    "create_case_proposal_activity",
    "offer_case_ownership_transfer_activity",
    "offer_case_participant_role_activity",
    "propose_case_ownership_transfer_activity",
    "reject_case_ownership_transfer_activity",
    "reject_case_participant_role_activity",
    "reject_case_proposal_activity",
    "reject_close_case_activity",
    "rm_accept_full_case_invite_activity",
    "rm_accept_invite_to_case_activity",
    "rm_close_case_activity",
    "rm_defer_case_activity",
    "rm_engage_case_activity",
    "rm_invite_to_case_activity",
    "rm_invite_to_full_case_activity",
    "rm_reject_full_case_invite_activity",
    "rm_reject_invite_to_case_activity",
    "rm_tentative_reject_full_case_invite_activity",
    "undo_case_ownership_transfer_activity",
    "update_case_activity",
]
