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


"""Carry the proofs the inbox verified to the record that archives them.

The inbox verifies a delivery in its route, before the body is parsed
(SIG-03-003), and the delivery is archived later, in the background run's
outcome stage, or later still, by a replay of the record it was held in.
:class:`VerifiedProofs` is the one narrow seam between them for one inbox
run: the route's proofs are noted under the activity id, the outcome port
writes them in the archive's own save
(:func:`~vultron.core.services.received_outcome.archive_applied`), and a
delivery left in holding keeps them on its record
(:func:`~vultron.core.services.received_holding.keep_verified_proofs`), so
the replay that archives it notes them again from there (SIG-03-004).
A refused delivery's receipt stub keeps none.
"""

from collections.abc import Sequence
from typing import cast

from vultron.core.models.verified_proof import VerifiedProof
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.services.received_activity import held_received_record
from vultron.core.services.received_holding import keep_verified_proofs


class VerifiedProofs:
    """The proofs verified on each delivery of one inbox run, by activity id.

    Not thread-safe: one inbox run uses it, under the actor's inbox lock.
    """

    def __init__(self) -> None:
        self._by_activity: dict[str, tuple[VerifiedProof, ...]] = {}

    def note(
        self, activity_id: str | None, proofs: Sequence[VerifiedProof]
    ) -> None:
        """Note that *proofs* verified on the delivery of *activity_id*."""
        if activity_id and proofs:
            self._by_activity[activity_id] = tuple(proofs)

    def of(self, activity_id: str) -> tuple[VerifiedProof, ...]:
        """The proofs noted for *activity_id*; empty when none were."""
        return self._by_activity.get(activity_id, ())

    def note_held(self, dl: DataLayer, activity_id: str) -> None:
        """Note the proofs *activity_id*'s held record carries, for its replay."""
        record = held_received_record(cast(CasePersistence, dl), activity_id)
        if record is not None:
            self.note(activity_id, record.verified_proofs)

    def keep_on_hold(self, dl: DataLayer, activity_id: str) -> None:
        """Keep the noted proofs on *activity_id*'s record if it is in holding."""
        keep_verified_proofs(
            cast(CasePersistence, dl), activity_id, self.of(activity_id)
        )


def payload_activity_id(payload: object) -> str | None:
    """The ``id`` a delivery's JSON body names, if it names one."""
    if isinstance(payload, dict):
        activity_id = payload.get("id")
        if isinstance(activity_id, str) and activity_id:
            return activity_id
    return None


__all__ = ["VerifiedProofs", "payload_activity_id"]
