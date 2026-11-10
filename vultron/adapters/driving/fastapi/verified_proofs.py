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


"""Carry the proofs the inbox verified to the record that keeps them.

The inbox verifies a delivery in its route, before the body is parsed
(SIG-03-003); the background run parses it later.  :class:`VerifiedProofs`
is the narrow seam between them for one inbox run: the route's proofs are
noted under the delivery's activity id, and the ingress adapter seals them
on the activity it parses from that body, beside its received evidence.
Intake then records them in the received record's first save, and every
later save of the record, a hold or the archive, keeps them (SIG-03-004).
A replay seals them again from the held record it rebuilds from.
"""

from collections.abc import Sequence

from vultron.core.models.verified_proof import VerifiedProof
from vultron.errors import VultronWiringError


class VerifiedProofs:
    """The proofs verified on each delivery of one inbox run, by activity id.

    Not thread-safe: one inbox run uses it, under the actor's inbox lock.
    """

    def __init__(self) -> None:
        self._by_activity: dict[str, tuple[VerifiedProof, ...]] = {}

    def note(
        self, activity_id: str | None, proofs: Sequence[VerifiedProof]
    ) -> None:
        """Note that *proofs* verified on the delivery of *activity_id*.

        Raises:
            VultronWiringError: *proofs* verified on a body that names no
                ``id``, so nothing could key them to its received record
                and they would be lost without a word (SIG-03-004).
        """
        if not proofs:
            return
        if not activity_id:
            raise VultronWiringError(
                "the inbox verified proofs on a delivery whose body names no"
                " id, so its received record could not keep them"
                " (SIG-03-004)"
            )
        self._by_activity[activity_id] = tuple(proofs)

    def of(self, activity_id: str) -> tuple[VerifiedProof, ...]:
        """The proofs noted for *activity_id*; empty when none were."""
        return self._by_activity.get(activity_id, ())


def payload_activity_id(payload: object) -> str | None:
    """The ``id`` a delivery's JSON body names, if it names one."""
    if isinstance(payload, dict):
        activity_id = payload.get("id")
        if isinstance(activity_id, str) and activity_id:
            return activity_id
    return None


__all__ = ["VerifiedProofs", "payload_activity_id"]
