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

"""Workflow step helpers shared across demo scenarios.

Provides generic CVD workflow actions — report submission, report validation,
and case lookup — that can be reused across rv, three-actor, and
multi-vendor demo scenarios.  Each function is named after the CVD role that
performs the action (reporter, coordinator) rather than after a scenario that
uses it.  This is where the demo's protocol activity lives.

Submodules
----------
- :mod:`.report` — report submission, the trusted-introduction check and the
  receiver's answer (validate / invalidate) to the report Offer.
- :mod:`.triage` — the receiver's RM triage: engaging the case on the direct
  and invite paths.
- :mod:`.case_lookup` — finding and waiting for the case a report or Offer
  produced.
- :mod:`.case_setup` — case creation and the stub-Invite seating chain that
  scenarios start from.
- :mod:`.participants` — the CASE_MANAGER, ownership-transfer Offers and
  two-participant case setup.
- :mod:`.embargo_decision` — the case owner's decision on an embargo proposal.
"""

from vultron.demo.helpers.workflow.case_lookup import (
    find_case_by_report_id,
    find_case_for_offer,
    wait_for_case_by_report,
    wait_for_case_for_offer,
)
from vultron.demo.helpers.workflow.case_setup import (
    create_case_via_trigger,
    invitee_declines_stub_invite,
    seat_participant_through_stub_invite,
    setup_canonical_case,
    setup_initialized_case,
    submit_validate_and_create_case,
)
from vultron.demo.helpers.workflow.embargo_decision import (
    owner_activates_embargo,
    owner_rejects_embargo_proposal,
)
from vultron.demo.helpers.workflow.participants import (
    await_ownership_transfer_offer,
    case_manager_invites_actor,
    find_case_manager_actor_id,
    setup_two_participant_case,
)
from vultron.demo.helpers.workflow.report import (
    check_report_answer_recorded,
    receiver_invalidates_report,
    receiver_validates_report,
    reporter_submits_report,
    verify_reporter_trusts_introduction,
    wait_for_report_answer_recorded,
)
from vultron.demo.helpers.workflow.triage import (
    receiver_engages_case,
    run_direct_path_rm_triage,
    run_invite_path_rm_triage,
)

__all__ = [
    "await_ownership_transfer_offer",
    "case_manager_invites_actor",
    "check_report_answer_recorded",
    "create_case_via_trigger",
    "find_case_by_report_id",
    "find_case_for_offer",
    "find_case_manager_actor_id",
    "invitee_declines_stub_invite",
    "owner_activates_embargo",
    "owner_rejects_embargo_proposal",
    "receiver_engages_case",
    "receiver_invalidates_report",
    "receiver_validates_report",
    "reporter_submits_report",
    "run_direct_path_rm_triage",
    "run_invite_path_rm_triage",
    "seat_participant_through_stub_invite",
    "setup_canonical_case",
    "setup_initialized_case",
    "setup_two_participant_case",
    "submit_validate_and_create_case",
    "verify_reporter_trusts_introduction",
    "wait_for_case_by_report",
    "wait_for_case_for_offer",
    "wait_for_report_answer_recorded",
]
