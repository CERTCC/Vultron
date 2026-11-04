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
Factory functions for outbound Vultron embargo-management activities.

These are the sole public construction API for activities involving
``as_EmbargoEvent`` objects. Internal activity subclasses are
imported in the submodules, grouped by concern, and MUST NOT be imported by
callers.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

from vultron.wire.as2.factories.embargo.lifecycle import (
    activate_embargo_activity,
    announce_embargo_activity,
    reject_embargo_proposal_activity,
    remove_embargo_from_case_activity,
    withdraw_from_embargo_activity,
)
from vultron.wire.as2.factories.embargo.negotiation import (
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
    em_undo_embargo_invite_activity,
)
from vultron.wire.as2.factories.embargo.records import (
    create_embargo_consent_activity,
    create_embargo_event_activity,
    update_embargo_consent_activity,
)

__all__ = [
    "activate_embargo_activity",
    "announce_embargo_activity",
    "create_embargo_consent_activity",
    "create_embargo_event_activity",
    "em_accept_embargo_activity",
    "em_propose_embargo_activity",
    "em_reject_embargo_activity",
    "em_undo_embargo_invite_activity",
    "reject_embargo_proposal_activity",
    "remove_embargo_from_case_activity",
    "update_embargo_consent_activity",
    "withdraw_from_embargo_activity",
]
