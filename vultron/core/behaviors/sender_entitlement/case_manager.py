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

"""The ``CASE_MANAGER`` kind's check (PCR-03-001, SYNC-13-006)."""

from typing import ClassVar

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.log_entry import require_log_entry
from vultron.core.behaviors.sender_entitlement.base import (
    SenderEntitlementConditionNode,
)
from vultron.core.behaviors.sender_entitlement.declarations import (
    SenderEntitlementKind,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.participants.authority import (
    established_link_case_manager_id,
    resolve_case_manager_id,
)
from vultron.core.predicates.addressing import (
    same_actor_id,
)
from vultron.errors import VultronError

# ---------------------------------------------------------------------------
# Condition node: CASE_MANAGER
# ---------------------------------------------------------------------------


class SenderIsCaseManagerNode(SenderEntitlementConditionNode):
    """Guard: sender must be the case's CASE_MANAGER.

    Resolves the case's authoritative CaseActor via
    :func:`~vultron.core.participants.authority.resolve_case_manager_id`
    and returns ``SUCCESS`` only when the announce ``actor_id`` equals that
    resolved CaseActor id.

    Passes through (``SUCCESS``) during the bootstrap window — when the case
    replica is not seeded yet, or no CASE_MANAGER is known — so downstream
    reject-on-missing-case / pre-genesis buffering (SYNC-15-001,
    SYNC-15-004) handles the entry rather than this gate dropping it.

    With ``anchored=True`` the sender must be the CASE_MANAGER this receiver
    has trusted for the case, and there is no pass-through (PCR-03-004).
    That is the CASE_MANAGER its bootstrap ``Create(VulnerabilityCase)``
    recorded on a completed ``ReportCaseLink``, which ordinary case traffic
    never replaces (CBT-01-006, CBT-02-003); else the replica's; else the
    one recorded as the case's trust anchor when the receiver got the stub
    Invite (#4185).  A sender with no anchor to match is refused.  The
    full-case Invite and ``Announce(VulnerabilityCase)`` use it: their
    sender is the one actor the bootstrap or the stub Invite introduced.
    Only the Announce reaches the stub-Invite fallback, since it is what
    creates the replica; the full-case Invite is judged only once the
    replica exists (CM-11-033), so the replica's CASE_MANAGER decides it.

    With ``required=True`` there is no pass-through either: a case this store
    does not hold, or one that names no CASE_MANAGER, leaves nothing to
    establish the sender's standing against, so the sender is refused
    (Regime 1, ADR-0087).  A reply to an ownership-transfer Offer uses it at a
    replica, which takes the ownership change from the CASE_MANAGER alone
    (PCR-03-001).

    The check that the CASE_MANAGER's own ``Announce(CaseLedgerEntry)``, echoed
    back to it, came from itself is this check too: the identity compared is
    the one :func:`resolve_case_manager_id` resolves for the case (#4437).

    Reads ``activity`` from the blackboard via INPUT_PORTS; the sender is its
    ``actor_id`` unless ``sender_actor_id`` names it.

    Merged from ``VerifySenderIsCaseActorNode`` (ADR-0115, AC-2).

    Spec: CLP-01-003, SYNC-13-006, HP-01-006, PCR-03-004, CBT-02-003.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.CASE_MANAGER
    )

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    def __init__(
        self,
        case_id: str | None = None,
        name: str | None = None,
        *,
        anchored: bool = False,
        required: bool = False,
        sender_actor_id: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case whose CASE_MANAGER the sender must be.
                Leave ``None`` for a ledger-entry activity, where the case is
                read from the entry the activity carries.
            name: Optional node name.
            anchored: Match the sender against the CASE_MANAGER the
                receiver's bootstrap recorded on a completed
                ``ReportCaseLink`` first (CBT-02-003), and refuse, rather than
                pass through, when neither that record, the replica nor a
                stub Invite's trust anchor names one (PCR-03-004).
            required: Refuse, rather than pass through, when this store holds
                no case or the case names no CASE_MANAGER.
            sender_actor_id: The sender to check.  ``None`` reads it from the
                blackboard activity's ``actor_id``; the composed guard passes
                the sender every other kind checks (HP-01-025).
        """
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._anchored = anchored
        self._required = required
        self._sender_actor_id = sender_actor_id

    def _recorded_anchor(self, case_id: str) -> str | None:
        """The CASE_MANAGER recorded when the receiver got the stub Invite.

        Only a stub Invite anchors trust (PCR-03-004 path b).  The
        pre-bootstrap queue shares the record and records the sender of the
        first deferred activity, which is no anchor until an Invite confirms
        it (``invite_anchored``).
        """
        assert self.datalayer is not None
        pending = self.datalayer.read(
            VultronPendingCaseInbox.build_id(case_id)
        )
        if isinstance(pending, VultronPendingCaseInbox) and (
            pending.invite_anchored
        ):
            return pending.case_actor_id
        return None

    def _trusted_case_manager(
        self, case_id: str, case: VulnerabilityCase | None
    ) -> str | None:
        """The CASE_MANAGER the sender must be, or ``None`` when none is known.

        An anchored check trusts the one the bootstrap recorded before the
        replica's, which ordinary traffic may rewrite (CBT-02-003), and falls
        back to the stub Invite's trust anchor (PCR-03-004).
        """
        assert self.datalayer is not None
        if self._anchored and (
            recorded := established_link_case_manager_id(
                self.datalayer, case_id
            )
        ):
            return recorded
        if case is not None and (
            holder := resolve_case_manager_id(case, self.datalayer)
        ):
            return holder
        return self._recorded_anchor(case_id) if self._anchored else None

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if self._case_id is not None:
            case_id = self._case_id
        else:
            try:
                entry = require_log_entry(self.activity, self.name)
            except VultronError as exc:
                self.logger.error(  # noqa: TRY400
                    "%s: %s", self.name, exc
                )
                return Status.FAILURE
            case_id = entry.case_id
        sender_id = self._sender_actor_id or getattr(
            self.activity, "actor_id", None
        )

        if not sender_id:
            self.logger.warning("%s: announce has no actor_id", self.name)
            return Status.FAILURE

        # Lenient read: a missing case is the bootstrap window (Regime 3,
        # ADR-0087) — pass through rather than starving buffer/reject paths.
        case = self.datalayer.read_case(case_id)
        case_actor_id = self._trusted_case_manager(case_id, case)

        if case_actor_id is None and self._anchored:
            return self._refuse_by_placement(
                f"No CASE_MANAGER is known for case '{case_id}' to"
                f" match sender '{sender_id}' — REFUSED (HP-01-006,"
                " PCR-03-004)"
            )

        if case_actor_id is None and self._required:
            held = (
                f"this store holds no case '{case_id}'"
                if case is None
                else f"case '{case_id}' names no CASE_MANAGER"
            )
            return self._refuse_by_placement(
                f"Sender '{sender_id}' has no standing: {held} — REFUSED"
                " (PCR-03-001, HP-01-006)"
            )

        if case_actor_id is None:
            self.logger.debug(
                "%s: no CaseActor known for case '%s'"
                " — passing through for bootstrap handling",
                self.name,
                case_id,
            )
            return Status.SUCCESS

        if same_actor_id(sender_id, case_actor_id):
            self.logger.debug(
                "%s: sender '%s' matches CaseActor for case '%s'",
                self.name,
                sender_id,
                case_id,
            )
            return Status.SUCCESS

        return self._refuse_by_placement(
            f"Sender '{sender_id}' is not the CASE_MANAGER for case"
            f" '{case_id}', which is '{case_actor_id}'"
            " — REFUSED (HP-01-006)"
        )
