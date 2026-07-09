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

"""Shared demo helper library.

Re-exports the full public surface of all sub-modules so callers can
import from ``vultron.demo.helpers`` directly.

Sub-modules
-----------
- :mod:`~vultron.demo.helpers.polling` — ``_poll_until`` and all
  ``wait_for_*`` helpers.
- :mod:`~vultron.demo.helpers.actions` — ``actor_notifies_state_change``
  and named CVD lifecycle action wrappers.
- :mod:`~vultron.demo.helpers.seeding` — ``_dl_key``, ``get_actor_by_id``,
  ``seed_containers``, ``seed_containers_fvv``, and ``reset_containers``.
- :mod:`~vultron.demo.helpers.sync` — SYNC-2 ``trigger_log_commit`` and
  ``verify_replica_state``.
- :mod:`~vultron.demo.helpers.verification` — lower-level participant and
  case-state assertion primitives, plus ``verify_receiver_case_state``
  and ``verify_case_actor_unused``.
- :mod:`~vultron.demo.helpers.workflow` — ``reporter_submits_report``,
  ``receiver_validates_report``, ``receiver_engages_case``, and
  ``find_case_for_offer``.
- :mod:`~vultron.demo.helpers.notes` — ``participant_adds_note_to_case``.
- :mod:`~vultron.demo.helpers.milestones` — lifecycle milestone verifiers
  (``verify_case_active``, ``verify_fix_ready``, ``verify_fix_deployed``,
  ``verify_publicly_disclosed``, ``verify_case_closed``).
"""

from vultron.demo.helpers.actions import (  # noqa: F401
    actor_closes_case,
    actor_notifies_fix_deployed,
    actor_notifies_fix_ready,
    actor_notifies_published,
    actor_notifies_state_change,
)
from vultron.demo.helpers.milestones import (  # noqa: F401
    verify_case_active,
    verify_case_closed,
    verify_fix_deployed,
    verify_fix_ready,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.notes import (  # noqa: F401
    participant_adds_note_to_case,
)
from vultron.demo.helpers.polling import (  # noqa: F401
    _poll_until,
    wait_for_all_participants_rm_closed,
    wait_for_case_em_terminated,
    wait_for_case_on_container,
    wait_for_case_participants,
    wait_for_finder_case,
    wait_for_finder_log_entry,
    wait_for_note_in_case,
    wait_for_participant_vfd_state,
)
from vultron.demo.helpers.seeding import (  # noqa: F401
    _dl_key,
    get_actor_by_id,
    reset_containers,
    seed_containers,
    seed_containers_fvv,
)
from vultron.demo.helpers.sync import (  # noqa: F401
    _extract_ref_id,
    _get_log_entries_for_case,
    trigger_log_commit,
    verify_finder_replica_state,
    verify_replica_state,
)
from vultron.demo.helpers.verification import (  # noqa: F401
    _all_fetchable_participants_rm_closed,
    _assert_case_notes,
    _assert_participant_vfd_pxa,
    _assert_vendor_case_status,
    _assert_vendor_participant_state,
    _check_participant_vfd_state_in,
    _fetch_participant,
    _fetch_participant_data,
    _require_case_participant_id,
    verify_case_actor_unused,
    verify_receiver_case_state,
)
from vultron.demo.helpers.workflow import (  # noqa: F401
    _load_case_from_datalayer,
    _report_id_from_offer_data,
    find_case_for_offer,
    receiver_engages_case,
    receiver_validates_report,
    reporter_submits_report,
)
