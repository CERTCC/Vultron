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
Public construction API for outbound Vultron protocol activities.

Factory functions in this package are the sole public API for building
outbound Vultron activities.  Internal activity subclasses in
``vultron/wire/as2/vocab/activities/`` are implementation details used
only inside factory functions — callers MUST NOT import them directly.
See ``specs/activity-factories.yaml`` AF-01-001, AF-02-001 through
AF-02-004.
"""

from vultron.wire.as2.factories.actor import (
    accept_actor_recommendation_activity,
    recommend_actor_activity,
    reject_actor_recommendation_activity,
)
from vultron.wire.as2.factories.case import (
    accept_case_manager_role_activity,
    accept_case_ownership_transfer_activity,
    add_note_to_case_activity,
    add_report_to_case_activity,
    add_status_to_case_activity,
    announce_vulnerability_case_activity,
    create_case_activity,
    create_case_status_activity,
    offer_case_manager_role_activity,
    offer_case_ownership_transfer_activity,
    reject_case_manager_role_activity,
    reject_case_ownership_transfer_activity,
    rm_accept_invite_to_case_activity,
    rm_close_case_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
    rm_invite_to_case_activity,
    rm_reject_invite_to_case_activity,
    update_case_activity,
)
from vultron.wire.as2.factories.case_participant import (
    add_participant_to_case_activity,
    add_status_to_participant_activity,
    create_participant_activity,
    create_status_for_participant_activity,
    remove_participant_from_case_activity,
)
from vultron.wire.as2.factories.embargo import (
    activate_embargo_activity,
    add_embargo_to_case_activity,
    announce_embargo_activity,
    choose_preferred_embargo_activity,
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
    remove_embargo_from_case_activity,
)
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.factories.report import (
    parse_submit_report_offer,
    rm_close_report_activity,
    rm_create_report_activity,
    rm_invalidate_report_activity,
    rm_read_report_activity,
    rm_submit_report_activity,
    rm_validate_report_activity,
)
from vultron.wire.as2.factories.sync import (
    announce_log_entry_activity,
    reject_log_entry_activity,
)

__all__ = [
    # errors
    "VultronActivityConstructionError",
    # actor
    "accept_actor_recommendation_activity",
    "recommend_actor_activity",
    "reject_actor_recommendation_activity",
    # case
    "accept_case_ownership_transfer_activity",
    "add_note_to_case_activity",
    "add_report_to_case_activity",
    "add_status_to_case_activity",
    "announce_vulnerability_case_activity",
    "create_case_activity",
    "create_case_status_activity",
    "offer_case_ownership_transfer_activity",
    "reject_case_ownership_transfer_activity",
    "rm_accept_invite_to_case_activity",
    "rm_close_case_activity",
    "rm_defer_case_activity",
    "rm_engage_case_activity",
    "rm_invite_to_case_activity",
    "rm_reject_invite_to_case_activity",
    "update_case_activity",
    # case_participant
    "add_participant_to_case_activity",
    "add_status_to_participant_activity",
    "create_participant_activity",
    "create_status_for_participant_activity",
    "remove_participant_from_case_activity",
    # embargo
    "activate_embargo_activity",
    "add_embargo_to_case_activity",
    "announce_embargo_activity",
    "choose_preferred_embargo_activity",
    "em_accept_embargo_activity",
    "em_propose_embargo_activity",
    "em_reject_embargo_activity",
    "remove_embargo_from_case_activity",
    # report
    "parse_submit_report_offer",
    "rm_close_report_activity",
    "rm_create_report_activity",
    "rm_invalidate_report_activity",
    "rm_read_report_activity",
    "rm_submit_report_activity",
    "rm_validate_report_activity",
    # sync
    "announce_log_entry_activity",
    "reject_log_entry_activity",
]
