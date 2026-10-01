#!/usr/bin/env python
#
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
"""Pre-seed the case for a peer that Rejected from genesis (SYNC-15-002).

Split from ``replay.py`` to keep that module under the submodule line cap
(CS-18-001); the node runs ahead of the replay in ``create_reject_log_entry_tree``.
"""

from __future__ import annotations

import logging
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.sync.nodes.embargo_pause import peer_is_withheld
from vultron.core.behaviors.sync.nodes.replay import _require_rejected_entry
from vultron.core.ports.case_persistence import (
    CaseOutboxPersistence,
    CasePersistence,
)
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.errors import VultronError, VultronValidationError

logger = logging.getLogger(__name__)


class AnnounceCaseOnGenesisRejectNode(DataLayerActionWithPorts):
    """Queue Announce(VulnerabilityCase) to a peer that rejected from genesis.

    When a peer sends ``Reject(last_accepted_hash="")`` it has no copy of
    VulnerabilityCase yet.  Replaying ledger entries without first seeding the
    case object causes ReconstructChainTailNode to fail again on every entry,
    producing an exponential reject-replay loop (SYNC-15-002).  This node
    fires first so the VulnerabilityCase arrives before the entry replay.

    Returns SUCCESS unconditionally (missing trigger port is only a WARNING so
    that the replay still runs in environments without a trigger port).

    Authored as the executing actor, gated on CASE_MANAGER (ADR-0073).
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
        "case_actor_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "activity": "/activity",
            "case_actor_id": "/case_actor_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")
        self.case_actor_id_bb: str = self.get_input("case_actor_id")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        activity = self.activity
        if activity.last_accepted_hash != "":
            return Status.SUCCESS

        factory = cast(
            TriggerActivityPort | None,
            self.trigger_activity_factory,
        )
        if factory is None:
            self.logger.warning(
                "%s: trigger_activity_factory not available;"
                " cannot pre-seed VulnerabilityCase for peer '%s' (SYNC-15-002)",
                self.name,
                activity.actor_id,
            )
            return Status.SUCCESS

        entry = _require_rejected_entry(activity, self.name)
        peer_id = activity.actor_id
        # CM-10-004: the case object is case content; a withheld peer's replay
        # is withheld too (SendMissingEntriesNode), so seed nothing.
        try:
            withheld = peer_is_withheld(
                cast(CasePersistence, self.datalayer),
                case_id=entry.case_id,
                peer_id=peer_id,
            )
        except VultronError as exc:
            self.feedback_message = str(exc)
            self.logger.exception("%s: embargo gate undecidable", self.name)
            return Status.FAILURE
        if withheld:
            self.logger.info(
                "%s: peer '%s' has not accepted the active embargo on case"
                " '%s'; not pre-seeding the case (CM-10-004)",
                self.name,
                peer_id,
                entry.case_id,
            )
            return Status.SUCCESS
        # `case_actor_id` is no longer read here: the announce is authored by the
        # executing actor (see below), not by a looked-up CaseActor. The input
        # port is left declared so the node's contract is unchanged for callers
        # that already populate it.

        try:
            activity_id = factory.announce_vulnerability_case(
                case_id=entry.case_id,
                # The executing actor, which the CASE_MANAGER gate has already
                # established holds that role — not a looked-up CaseActor id.
                actor=self.actor_id,
                context_id=entry.case_id,
                to=[peer_id],
            )
            cast(CaseOutboxPersistence, self.datalayer).outbox_append(
                activity_id
            )
            self.logger.info(
                "%s: queued AnnounceVulnerabilityCase '%s' to peer '%s'"
                " before entry replay (SYNC-15-002)",
                self.name,
                activity_id,
                peer_id,
            )
        except VultronValidationError:
            # The announce cannot be built from this actor's own records — for
            # example its case names an embargo its store cannot read
            # (EMB-18-003).  That is a broken invariant, not a transient
            # failure, so it is not logged as recoverable.
            self.logger.exception(
                "%s: refusing to queue AnnounceVulnerabilityCase for peer '%s'",
                self.name,
                peer_id,
            )
        except Exception as exc:  # noqa: BLE001  # ruff-baseline #3768
            self.logger.warning(
                "%s: could not queue AnnounceVulnerabilityCase for peer '%s': %s",
                self.name,
                peer_id,
                exc,
            )
        return Status.SUCCESS
