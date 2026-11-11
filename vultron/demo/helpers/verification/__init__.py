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

"""Scenario-verification primitives shared across demo workflows.

Lower-level assertion helpers used by milestone verification functions in the
individual scenario modules (e.g. ``rv_demo.py``).  Keeping them here
avoids duplication when future multi-actor scenarios need the same checks.

Submodules
----------
- :mod:`.participants` — fetching a case's participant records.
- :mod:`.states` — participant and case state assertions (RM, VF, D, PXA,
  EM, notes).
- :mod:`.records` — activity receipt, the receiver's final case state and
  the CaseActor's canonical records.
"""

from vultron.demo.helpers.verification.participants import (
    verify_participant_status_appended,
)
from vultron.demo.helpers.verification.records import (
    recipient_ids,
    verify_activity_in_inbox,
    verify_case_actor_holds_records,
    verify_receiver_case_state,
    verify_receiver_verified_sender_key,
)

__all__ = [
    "recipient_ids",
    "verify_activity_in_inbox",
    "verify_case_actor_holds_records",
    "verify_participant_status_appended",
    "verify_receiver_case_state",
    "verify_receiver_verified_sender_key",
]
