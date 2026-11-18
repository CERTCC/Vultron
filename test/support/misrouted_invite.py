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
"""A misrouted ``Invite(EmbargoEvent)``, which no factory builds (EP-09-026).

``em_propose_embargo_activity`` names the Invite's one recipient in
``target`` and refuses an Invite to several actors (EP-09-010, ADR-0205),
so a test of the receiver's misrouting refusal readdresses a well-formed
Invite instead.
"""

from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Invite,
)


def readdressed[I: as_Invite](invite: I, to: list[str]) -> I:
    """*invite* delivered to *to*, its ``target`` unchanged.

    The copy skips validation, as a hand-written wire body would: *to* may
    name no actor, several, or one other than the invitee ``target`` names.
    """
    return invite.model_copy(update={"to": to})
