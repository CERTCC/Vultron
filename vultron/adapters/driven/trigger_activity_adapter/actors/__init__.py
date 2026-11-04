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

"""Actor-domain trigger activity construction for TriggerActivityAdapter.

Covers actor invitations, recommendations, participant management, and
Case Actor / CASE_MANAGER delegation activities, one concern per submodule:

- :mod:`.invites` — case and full-case invitations and their answers
- :mod:`.participants` — participant offers, actor recommendations, and
  participant membership and status
- :mod:`.roles` — participant-role offers and their answers
- :mod:`.ownership` — case ownership transfer
"""

from .invites import _InvitesMixin
from .ownership import _OwnershipMixin
from .participants import _ParticipantsMixin
from .roles import _RolesMixin


class _ActorsMixin(
    _InvitesMixin,
    _ParticipantsMixin,
    _RolesMixin,
    _OwnershipMixin,
):
    """Trigger activity methods for actor invitations, recommendations,
    participant management, and CASE_MANAGER delegation.
    """
