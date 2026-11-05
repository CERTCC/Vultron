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

"""Polling helpers for demo workflows.

Every ``wait_for_*`` / ``find_*`` helper the demo scenarios gate on, grouped
by what they wait on.  All of them bottom out in the shared primitives in
:mod:`._poll` (``_poll_until``, ``_poll_datalayer_for``), so there is a
single place to tune timeout and interval defaults.

Submodules
----------
- :mod:`._poll` — timeout constants, ``ProgressDeadline``, ``SharedBudget``
  and the polling loops.
- :mod:`.case_actor` — locating the CaseActor and its store.
- :mod:`.case` — case replica arrival, participants, notes and owner.
- :mod:`.ledger` — ledger entries, events and contiguous coverage.
- :mod:`.received` — stored objects and received activities.
- :mod:`.finders` — received Invite and Offer finders.
- :mod:`.participant` — participant RM, VF, D and PXA states.
- :mod:`.embargo` — case EM state, embargo proposals and consent.
"""

from vultron.demo.helpers.polling._poll import (
    BACKFILL_PROGRESS_CEILING,
    CROSS_CONTAINER_TIMEOUT,
    EM_TRANSITION_TIMEOUT,
    LATE_JOINER_COVERAGE_TIMEOUT,
    LATE_JOINER_REPLICA_TIMEOUT,
    LATE_JOINER_TIMEOUT,
    LEDGER_COVERAGE_TIMEOUT,
    PARTICIPANT_JOIN_TIMEOUT,
    REPLICA_PARTICIPANT_TIMEOUT,
    ProgressDeadline,
    SharedBudget,
)
from vultron.demo.helpers.polling.case import (
    wait_for_case_attributed_to,
    wait_for_case_on_container,
    wait_for_case_participants,
    wait_for_initialized_case,
    wait_for_note_in_case,
    wait_for_participants_on_replicas,
    wait_for_pending_inbox_quiescent,
    wait_for_reporter_case,
)
from vultron.demo.helpers.polling.case_actor import (
    case_actor_participant_id_in,
    case_manager_store,
    find_case_actor_participant_id,
    resolve_case_actor_store_id,
)
from vultron.demo.helpers.polling.embargo import (
    wait_for_case_em_state,
    wait_for_case_em_terminated,
    wait_for_embargo_proposal_indexed,
    wait_for_participant_embargo_accepted,
    wait_for_participant_embargo_consent,
)
from vultron.demo.helpers.polling.finders import (
    find_case_invite_for_actor,
    find_cp_offer_for_case,
    find_embargo_invite_for_actor,
    find_full_case_invite_for_actor,
    find_ownership_transfer_offer_for_actor,
)
from vultron.demo.helpers.polling.ledger import (
    wait_for_case_actor_ledger_event,
    wait_for_contiguous_ledger_coverage,
    wait_for_ledger_event,
    wait_for_reporter_log_entry,
    wait_for_semantic_type_in_ledger,
)
from vultron.demo.helpers.polling.participant import (
    ParticipantDimension,
    wait_for_all_participants_rm_closed,
    wait_for_participant_d_state,
    wait_for_participant_pxa_state,
    wait_for_participant_rm_state,
    wait_for_participant_vf_state,
)
from vultron.demo.helpers.polling.received import (
    assert_received_from,
    read_received_activity_for,
    wait_for_object_stored,
    wait_for_received_activity,
    wait_for_report_submission_stored,
    wait_for_reporter_introduction,
)

__all__ = [
    "BACKFILL_PROGRESS_CEILING",
    "CROSS_CONTAINER_TIMEOUT",
    "EM_TRANSITION_TIMEOUT",
    "LATE_JOINER_COVERAGE_TIMEOUT",
    "LATE_JOINER_REPLICA_TIMEOUT",
    "LATE_JOINER_TIMEOUT",
    "LEDGER_COVERAGE_TIMEOUT",
    "PARTICIPANT_JOIN_TIMEOUT",
    "ParticipantDimension",
    "ProgressDeadline",
    "REPLICA_PARTICIPANT_TIMEOUT",
    "SharedBudget",
    "assert_received_from",
    "case_actor_participant_id_in",
    "case_manager_store",
    "find_case_actor_participant_id",
    "find_case_invite_for_actor",
    "find_cp_offer_for_case",
    "find_embargo_invite_for_actor",
    "find_full_case_invite_for_actor",
    "find_ownership_transfer_offer_for_actor",
    "read_received_activity_for",
    "resolve_case_actor_store_id",
    "wait_for_all_participants_rm_closed",
    "wait_for_case_actor_ledger_event",
    "wait_for_case_attributed_to",
    "wait_for_case_em_state",
    "wait_for_case_em_terminated",
    "wait_for_case_on_container",
    "wait_for_case_participants",
    "wait_for_contiguous_ledger_coverage",
    "wait_for_embargo_proposal_indexed",
    "wait_for_initialized_case",
    "wait_for_ledger_event",
    "wait_for_note_in_case",
    "wait_for_object_stored",
    "wait_for_participant_d_state",
    "wait_for_participant_embargo_accepted",
    "wait_for_participant_embargo_consent",
    "wait_for_participant_pxa_state",
    "wait_for_participant_rm_state",
    "wait_for_participant_vf_state",
    "wait_for_participants_on_replicas",
    "wait_for_pending_inbox_quiescent",
    "wait_for_received_activity",
    "wait_for_report_submission_stored",
    "wait_for_reporter_case",
    "wait_for_reporter_introduction",
    "wait_for_reporter_log_entry",
    "wait_for_semantic_type_in_ledger",
]
