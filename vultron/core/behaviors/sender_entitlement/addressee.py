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

"""The ``NAMED_ACTOR`` kind: the addressee of a recorded request (HP-01-009).

The shared base compares the sender with the addressees its subclass
reads from one kind of recorded request, and words the refusal.
"""

from dataclasses import dataclass
from typing import ClassVar

from py_trees.common import Status

from vultron.core.behaviors.sender_entitlement.base import (
    SenderEntitlementConditionNode,
)
from vultron.core.behaviors.sender_entitlement.declarations import (
    SenderEntitlementKind,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.participants.authority import (
    resolve_case_manager_id,
)
from vultron.core.participants.recipients import (
    closure_recorded,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import (
    is_addressed_to,
)
from vultron.core.services.case_replica_seeding import expected_case_creators
from vultron.errors import VultronError

# ---------------------------------------------------------------------------
# Condition nodes: NAMED_ACTOR (the addressee of a recorded request)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecordedRequest:
    """The request a reply answers, as this store recorded it.

    Attributes:
        description: The request as a refusal names it, e.g.
            ``"Offer 'https://…'"``.
        position: The entitled sender as a refusal names it, e.g.
            ``"an addressee"`` or ``"the transferee"``.
        addressees: The actors entitled to answer it.
    """

    description: str
    position: str
    addressees: tuple[str, ...]


@dataclass(frozen=True)
class NothingToProtect:
    """This store made no such request, so there is no standing to check.

    Attributes:
        reason: Why, for the debug log.
    """

    reason: str


class NoStandingError(VultronError):
    """The sender's standing cannot be established; the message says why."""


class SenderIsRequestAddresseeNode(SenderEntitlementConditionNode):
    """Guard: sender must be an addressee of the request it answers.

    The one guard shape of the ``NAMED_ACTOR`` kind (HP-01-009, ADR-0129).
    Each subclass reads one kind of record this store holds for the request
    (:meth:`_recorded_request`); this base compares the sender with the
    record's addressees and words the refusal, so every addressee check
    compares and refuses the same way.  The record is this store's own,
    never the copy of the request the reply embeds, which the sender wrote.

    - A record that names the sender: ``SUCCESS``.
    - A record that does not, or names no one: ``FAILURE``, naming the
      request and its addressees.
    - No record the sender could stand on (:class:`NoStandingError`):
      ``FAILURE`` with that reason.
    - :class:`NothingToProtect`: ``SUCCESS``; a subclass returns it only
      where an unrecorded request has nothing to protect.

    Spec: HP-01-006, HP-01-009.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.NAMED_ACTOR
    )

    _spec: ClassVar[str]
    """The requirement a refusal cites; each subclass names its own."""

    def __init__(
        self,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.sender_actor_id = sender_actor_id

    def _recorded_request(self) -> RecordedRequest | NothingToProtect:
        """The request as this store recorded it.

        Raises:
            NoStandingError: This store holds no record the sender's
                standing could rest on.
        """
        raise NotImplementedError

    def _confirm_standing(self, request: RecordedRequest) -> None:
        """Check any standing the sender needs beyond being the addressee.

        Runs once the sender is known to be an addressee of *request*.

        Raises:
            NoStandingError: The sender lacks that standing.
        """

    def _refuse_citing(self, reason: str) -> Status:
        """Append the subclass's citation to *reason*, then refuse by placement.

        One ``_refuse_citing`` per citation across the family, never a
        ``_refuse``: see
        :meth:`SenderEntitlementConditionNode._refuse_by_placement`.
        """
        return self._refuse_by_placement(
            f"{reason} — REFUSED ({self._spec}, HP-01-006)"
        )

    def _confirm_addressee(self, request: RecordedRequest) -> None:
        """The one comparison every addressee check makes.

        Raises:
            NoStandingError: The sender is not among *request*'s addressees.
        """
        sender = self.sender_actor_id
        if is_addressed_to(sender, request.addressees):
            return
        shown = ", ".join(f"'{a}'" for a in request.addressees) or "nobody"
        raise NoStandingError(
            f"Sender '{sender}' is not {request.position} of"
            f" {request.description} ({shown})"
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        try:
            request = self._recorded_request()
            if isinstance(request, NothingToProtect):
                self.logger.debug(
                    "%s: %s — nothing to protect", self.name, request.reason
                )
                return Status.SUCCESS
            self._confirm_addressee(request)
            self._confirm_standing(request)
        except NoStandingError as exc:
            return self._refuse_citing(str(exc))
        return Status.SUCCESS


class SenderIsProposalAddresseeNode(SenderIsRequestAddresseeNode):
    """Guard: sender must be the actor the CaseProposal was addressed to.

    The vendor records the addressee on its ``VultronReportCaseLink``
    (``case_creator_id``) when it proposes the case.

    - No link for the report (a relay, or a proposal this actor never made):
      ``SUCCESS``, because there is nothing to protect and the effect node
      reports the no-op as ``SKIPPED``.
    - A link with no recorded addressee: ``FAILURE`` (nobody is entitled).
    - Any other sender: ``FAILURE``, so the tree ends ``REFUSED`` with the
      link unchanged.

    Spec: CP-06-005, HP-01-006.
    """

    _spec = "CP-06-005"

    def __init__(
        self,
        report_id: str,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(sender_actor_id=sender_actor_id, name=name)
        self.report_id = report_id

    def _recorded_request(self) -> RecordedRequest | NothingToProtect:
        assert self.datalayer is not None
        link = self.datalayer.read(
            VultronReportCaseLink.build_id(self.report_id)
        )
        if not isinstance(link, VultronReportCaseLink):
            return NothingToProtect(
                f"no report case link for '{self.report_id}'"
            )
        addressee = link.case_creator_id
        return RecordedRequest(
            description=f"the CaseProposal for report '{self.report_id}'",
            position="the addressee",
            addressees=(addressee,) if addressee is not None else (),
        )


class SenderIsExpectedCaseCreatorNode(SenderIsRequestAddresseeNode):
    """Guard: the sender of a bootstrap ``Create(VulnerabilityCase)`` is the
    actor this store expects the case from.

    The bootstrap answers the request that asked for the case: the vendor's
    ``CaseProposal`` to the case actor service, or the reporter's report
    ``Offer`` to the report receiver.  Either way the receiver recorded the
    request's addressee on a ``VultronReportCaseLink`` (``case_creator_id``)
    before the case arrived, and that record is its trust anchor
    (CBT-01-005).  The sender is admitted when a link still awaiting a
    bootstrap names it, or when a link already bound to the case names it (a
    redelivery, CBT-01-006).  Any other sender is refused and nothing is
    stored, whatever the snapshot it carries claims (CBT-01-011, ADR-0132).
    Which of the two the sender is, and whether its case references the
    report, are the received tree's to decide after admission.

    Spec: CBT-01-005, CBT-01-011, HP-01-006, HP-01-009.
    """

    _spec = "CBT-01-011"

    def __init__(
        self,
        case_id: str,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(sender_actor_id=sender_actor_id, name=name)
        self.case_id = case_id

    def _recorded_request(self) -> RecordedRequest:
        assert self.datalayer is not None
        return RecordedRequest(
            description=f"case '{self.case_id}'",
            position="the creator a trust anchor this actor wrote expects",
            addressees=tuple(
                expected_case_creators(self.datalayer, self.case_id)
            ),
        )


class SenderIsOfferAddresseeNode(SenderIsRequestAddresseeNode):
    """Guard: sender must be an actor the ``Offer(VulnerabilityReport)`` was
    addressed to.

    ``RK`` (``Read(Offer(VulnerabilityReport))``) is sent by the actor that
    received the report submission, to the reporter (RMB-08-003).  The
    reporter holds the Offer it sent, so this guard reads this store's
    :class:`~vultron.core.models.offer_record.VultronOfferRecord` for the
    acknowledged Offer and admits only one of its ``offer_to`` recipients.

    A store that holds no record of the Offer has nothing to establish the
    sender's standing against, so the sender is refused.

    Spec: RMB-08-004, HP-01-006.
    """

    _spec = "RMB-08-004"

    def __init__(
        self,
        offer_id: str | None,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            offer_id: The Offer the acknowledgement names (``None`` when it
                names none, which refuses).
            sender_actor_id: The acknowledgement's sender.
            name: Optional node name.
        """
        super().__init__(sender_actor_id=sender_actor_id, name=name)
        self.offer_id = offer_id

    def _recorded_request(self) -> RecordedRequest:
        assert self.datalayer is not None
        if self.offer_id is None:
            raise NoStandingError(
                f"Acknowledgement from '{self.sender_actor_id}' names no Offer"
            )
        record = self.datalayer.read(
            VultronOfferRecord.build_id(self.offer_id)
        )
        if not isinstance(record, VultronOfferRecord):
            raise NoStandingError(
                f"No record of Offer '{self.offer_id}' in this store, so"
                f" sender '{self.sender_actor_id}' cannot be shown to be its"
                " addressee"
            )
        return RecordedRequest(
            description=f"Offer '{self.offer_id}'",
            position="an addressee",
            addressees=tuple(record.offer_to),
        )


# ---------------------------------------------------------------------------
# Condition nodes: the answerer of an Offer the CASE_MANAGER recorded
# ---------------------------------------------------------------------------


def _case_and_manager(
    dl: CasePersistence, case_id: str, sender: str
) -> tuple[VulnerabilityCase, str]:
    """The case a reply names and its CASE_MANAGER, as this store holds them.

    Raises:
        NoStandingError: This store holds no such case, or the case names no
            CASE_MANAGER: there is nothing to establish the sender's standing
            against, which is a refusal and not a local anomaly.
    """
    case = dl.read_case(case_id)
    if case is None:
        raise NoStandingError(
            f"Sender '{sender}' has no standing: this store holds no"
            f" case '{case_id}'"
        )
    manager_id = resolve_case_manager_id(case, dl)
    if manager_id is None:
        raise NoStandingError(
            f"Sender '{sender}' has no standing: case '{case_id}'"
            " names no CASE_MANAGER"
        )
    return case, manager_id


def _refuse_if_closed(
    dl: CasePersistence, case: VulnerabilityCase, sender: str, position: str
) -> None:
    """Refuse an answerer whose closure the case records (CM-23-018).

    Raises:
        NoStandingError: *sender* has left the case (RM ``CLOSED``).
    """
    if closure_recorded(case, dl, sender):
        raise NoStandingError(
            f"{position} '{sender}' has left case '{case.id_}' (RM CLOSED)"
            " and may answer nothing further (CM-23-018)"
        )
