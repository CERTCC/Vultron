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

"""The canonical example of the ``Redacted`` marker (MV-12-003, ADR-0193).

The marker is a value in a preview's field, never an object of its own, so
this example shows its wire form only.
"""

from vultron.core.models.redacted import Redacted


def redacted_marker() -> Redacted:
    """A marker withholding a preview field's value, with the reason why."""
    return Redacted(summary="Withheld until the invitee accepts the embargo")
