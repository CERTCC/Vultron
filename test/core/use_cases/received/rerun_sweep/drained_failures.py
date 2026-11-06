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

"""The drained scenarios pinned as known failures: none (#5047).

When the outbox is delivered between runs, as the inbox's drain after every
delivery does, a later run must commit nothing new and send nothing under a
new id; a re-send under the first run's id with the same sealed body is
dropped by the receiver, so it is not a second send (#5047 AC-1 as
reworded).  Every scenario of the sweep meets that, so this table is empty,
and ``test_no_drained_scenario_is_pinned`` keeps it empty: a scenario that
sends again is fixed, never pinned as a known failure.
"""

from vultron.core.models.events.base import MessageSemantics

#: (path, kind, semantic) -> why it may send again.  Must stay empty.
DRAINED_FAILURES: dict[tuple[str, str, MessageSemantics], str] = {}


__all__ = ["DRAINED_FAILURES"]
