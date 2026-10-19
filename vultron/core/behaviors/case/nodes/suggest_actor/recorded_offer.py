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

"""The recorded Offer a Case Owner's answer names: one producer, one consumer mixin.

The Case Owner answers an ``Offer(CaseParticipant)`` with an ``Accept`` or a
``Reject`` (CM-16-006, CM-16-007).  What the CASE_MANAGER does next comes from
its own records, never from the answer's copy of the Offer: the invitee and
its roles from the Offer it recorded when it forwarded the recommendation
(ISSUE-1745, CM-16-019), and the recommender from the
:class:`ActorRecommendationRecord` it kept for that recommendation.

:class:`RequireRecordedOfferAnswerNode` looks both up as a precondition guard
of the answer's one received tree (CLP-10-005, CLP-10-010), so an answer
naming an Offer or recommendation this CASE_MANAGER never recorded is archived
by intake and refused before the commit, with nothing sent (CLP-10-018).  On
success it publishes a :class:`RecordedOfferAnswer`, and every later node
reads it through :class:`RecordedOfferAnswerInputMixin` instead of repeating
the lookup.
"""

from dataclasses import dataclass
from typing import Any, Literal

from py_trees.common import Status
from py_trees.ports import PortInformation

from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.models.actor_recommendation_record import (
    ActorRecommendationRecord,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.ports.case_persistence import CasePersistence
from vultron.enums.roles import serialize_roles
from vultron.errors import VultronError, VultronWiringError

#: The Case Owner's two answers to an ``Offer(CaseParticipant)``.
OfferAnswerVerb = Literal["Accept", "Reject"]


@dataclass(frozen=True)
class RecordedOfferAnswer:
    """What the CASE_MANAGER recorded about the Offer an answer names.

    Attributes:
        recommendation_id: The original ``Offer(Actor, Case)``, carried as
            the answered Offer's ``origin`` (CM-16-004).
        recommender_id: The participant that made the recommendation, from
            the CASE_MANAGER's :class:`ActorRecommendationRecord`.
        invitee_id: The recommended actor, from the recorded Offer.
        roles: The roles the recorded Offer carries, serialized; empty when
            it carries none.
    """

    recommendation_id: str
    recommender_id: str
    invitee_id: str
    roles: tuple[str, ...] = ()


class UnrecordedOfferAnswerError(VultronError):
    """An answer names an Offer or recommendation this store never recorded.

    The message completes "``<verb>(Offer(CaseParticipant))`` names ...".
    """


def recorded_offer_answer_key(answer_id: str) -> str:
    """The blackboard key holding the recorded Offer for one answer.

    Namespaced by the answer's id segment, as ``suggested_roles_key`` is, so
    one answer's lookup never reads another's.  No leading slash; a port
    remapping prefixes one.
    """
    return f"recorded_offer_answer_{answer_id.rsplit('/', maxsplit=1)[-1]}"


def _ref_id(value: object) -> object:
    """The id of *value*, whether it is an inline object or a bare id."""
    return getattr(value, "id_", value)


def _is_managers_offer_about(
    dl: CasePersistence, stored_offer: object, case: VulnerabilityCase
) -> bool:
    """True when *stored_offer* was sent by *case*'s CASE_MANAGER about it."""
    if stored_offer is None:
        return False
    manager_id = resolve_case_manager_id(case, dl)
    return (
        manager_id is not None
        and _ref_id(getattr(stored_offer, "actor", None)) == manager_id
        and _ref_id(getattr(stored_offer, "target", None)) == case.id_
    )


def recorded_invitee(
    dl: CasePersistence, inner_offer: object, case: VulnerabilityCase
) -> tuple[str, tuple[str, ...]]:
    """``(invitee_id, roles)`` from the Offer this CASE_MANAGER recorded.

    Found by the id the answer names, never from the answer's own copy of
    the Offer: the sender may have altered that copy or sent a bare
    reference (ISSUE-1745, CM-16-019).  Intake archives every inbound
    activity, refused ones included, so a stored object is "recorded" only
    when the case's CASE_MANAGER sent it about this case: an archived Offer
    from any other actor is not a record (CM-16-019).

    Raises:
        UnrecordedOfferAnswerError: the answer names no Offer this
            CASE_MANAGER recorded, or the recorded Offer names no invitee.
    """
    raw_offer_id = getattr(inner_offer, "id_", None)
    stored_offer = (
        dl.read(raw_offer_id)
        if isinstance(raw_offer_id, str) and raw_offer_id
        else None
    )
    unrecorded = UnrecordedOfferAnswerError(
        f"an Offer(CaseParticipant) this CASE_MANAGER never recorded"
        f" ({raw_offer_id})"
    )
    if not _is_managers_offer_about(dl, stored_offer, case):
        raise unrecorded
    stored_participant = getattr(stored_offer, "object_", None)
    # AKM-03-003: dehydration stores object_ as a bare ID string;
    # follow the reference to retrieve the full CaseParticipant.
    if isinstance(stored_participant, str):
        stored_participant = dl.read(stored_participant)
    invitee_id = _ref_id(getattr(stored_participant, "attributed_to", None))
    if not isinstance(invitee_id, str) or not invitee_id:
        raise unrecorded
    raw_roles = getattr(stored_participant, "roles", None)
    roles = (
        tuple(serialize_roles(raw_roles))
        if isinstance(raw_roles, list) and raw_roles
        else ()
    )
    return invitee_id, roles


def recorded_recommendation(
    dl: CasePersistence, inner_offer: object, case_id: str
) -> tuple[str, str]:
    """``(recommendation_id, recommender_id)`` for an answered Offer.

    The answered Offer carries the original ``Offer(Actor)`` id as
    ``origin`` (CM-16-004), and the recommender is whatever
    :class:`ActorRecommendationRecord` this CASE_MANAGER kept for the case
    when that recommendation arrived (case bookkeeping, CLP-07-014).
    CM-16-006/007 step 3 sends the decision to that recommender, so an
    answer whose Offer names no ``origin``, or an ``origin`` with no such
    record, has nobody to notify.

    Raises:
        UnrecordedOfferAnswerError: no ``origin``, or no record of it.
    """
    recommendation_id = _ref_id(getattr(inner_offer, "origin", None))
    if not isinstance(recommendation_id, str) or not recommendation_id:
        raise UnrecordedOfferAnswerError(
            "no recommendation (its inner Offer has no origin)"
        )
    record = dl.read(
        ActorRecommendationRecord.build_id(case_id, recommendation_id)
    )
    if not isinstance(record, ActorRecommendationRecord):
        raise UnrecordedOfferAnswerError(
            f"a recommendation this CASE_MANAGER never recorded"
            f" ({recommendation_id})"
        )
    return recommendation_id, record.recommender_id


class RequireRecordedOfferAnswerNode(DataLayerActionWithPorts):
    """Guard: the answered Offer and its recommendation are on record.

    Reads the received answer from ``/activity``, looks up the Offer it names
    (:func:`recorded_invitee`) and the recommendation behind it
    (:func:`recorded_recommendation`), and publishes the result under
    :func:`recorded_offer_answer_key`.  An Accept checks the Offer first and
    a Reject the recommendation first, so each reports the reason it always
    has when both are missing.

    FAILURE, with ``"<verb>(Offer(CaseParticipant)) names ..."`` as the
    reason, when either is not on record.  The output is a blackboard key,
    not a DataLayer write, so the node is safe among a received tree's
    ``precondition_guards`` (CLP-10-009): a refusal leaves no ledger entry.
    """

    def __init__(
        self,
        verb: OfferAnswerVerb,
        answer_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.verb = verb
        self.case_id = case_id
        self._answer_key = recorded_offer_answer_key(answer_id)
        self._activity: object | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=False),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "recorded_offer_answer": PortInformation(
            data_type=object, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def _instance_port_remappings(self) -> dict[str, str]:
        return {"recorded_offer_answer": f"/{self._answer_key}"}

    def initialise(self) -> None:
        super().initialise()
        self._activity = self._try_get_input("activity")

    def _lookup(
        self, dl: CasePersistence, case: VulnerabilityCase
    ) -> RecordedOfferAnswer:
        inner_offer = getattr(
            getattr(self._activity, "activity", None), "object_", None
        )
        if self.verb == "Accept":
            invitee_id, roles = recorded_invitee(dl, inner_offer, case)
            recommendation_id, recommender_id = recorded_recommendation(
                dl, inner_offer, self.case_id
            )
        else:
            recommendation_id, recommender_id = recorded_recommendation(
                dl, inner_offer, self.case_id
            )
            invitee_id, roles = recorded_invitee(dl, inner_offer, case)
        return RecordedOfferAnswer(
            recommendation_id=recommendation_id,
            recommender_id=recommender_id,
            invitee_id=invitee_id,
            roles=roles,
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: the CASE_MANAGER holds its case
        try:
            answer = self._lookup(self.datalayer, case)
        except UnrecordedOfferAnswerError as exc:
            self.feedback_message = (
                f"{self.verb}(Offer(CaseParticipant)) names {exc}"
            )
            self.logger.warning(
                "%s: event '%s' names %s — refusing",
                self.name,
                getattr(self._activity, "activity_id", None),
                exc,
            )
            return Status.FAILURE
        self._set_output("recorded_offer_answer", answer)
        return Status.SUCCESS


class RecordedOfferAnswerInputMixin:
    """Read the :class:`RecordedOfferAnswer` the guard published.

    A node that mixes this in calls :meth:`_read_answer_of` with the
    answer's id in its constructor and reads the answer through
    :meth:`_recorded_answer`.  The port is optional so a missing publisher
    is reported by :meth:`update`, never as a port-wiring error at setup:
    with nothing published under the node's key it raises
    :class:`~vultron.errors.VultronWiringError` before the node does
    anything, and the bridge reports that as an internal error, never a
    refusal (#2255).
    """

    # Annotation only: binding a value here would make every class that mixes
    # this in look like it had declared its ports (py_trees' abstract check).
    INPUT_PORTS: dict[str, PortInformation]
    _answer_key: str
    #: The published answer, read in ``initialise()``; ``None`` before.
    _recorded: RecordedOfferAnswer | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # As in ``CaseIdInputPortMixin``: add the port to whatever
        # ``INPUT_PORTS`` the class ends up with, before the ports base
        # validates them.
        cls.INPUT_PORTS = {
            **cls.INPUT_PORTS,
            "recorded_offer_answer": PortInformation(
                data_type=object, required=False
            ),
        }
        super().__init_subclass__(**kwargs)

    def _read_answer_of(self, answer_id: str) -> None:
        """Read the recorded Offer published for the answer *answer_id*."""
        self._answer_key = recorded_offer_answer_key(answer_id)

    def _instance_port_remappings(self) -> dict[str, str]:
        remappings = dict(super()._instance_port_remappings())  # type: ignore[misc]
        remappings["recorded_offer_answer"] = f"/{self._answer_key}"
        return remappings

    def initialise(self) -> None:
        super().initialise()  # type: ignore[misc]
        value = self._try_get_input("recorded_offer_answer")  # type: ignore[attr-defined]
        self._recorded = (
            value if isinstance(value, RecordedOfferAnswer) else None
        )

    def update(self) -> Status:
        """Refuse to run without the published answer, then run the node.

        Checked here, ahead of the node's own ``update()``, because an emit
        node catches what its build raises and would report the composition
        error as an ordinary FAILURE (#2255).
        """
        self._recorded_answer()
        status: Status = super().update()  # type: ignore[misc]
        return status

    def _recorded_answer(self) -> RecordedOfferAnswer:
        """The published answer.

        Raises:
            VultronWiringError: no answer is published under this node's
                key, so :class:`RequireRecordedOfferAnswerNode` did not run
                first — a tree composition error.
        """
        answer = self._recorded
        if answer is None:
            raise VultronWiringError(
                f"{getattr(self, 'name', type(self).__name__)}: no recorded"
                f" Offer answer at '/{self._answer_key}';"
                " RequireRecordedOfferAnswerNode must run first"
            )
        return answer


__all__ = [
    "OfferAnswerVerb",
    "RecordedOfferAnswer",
    "RecordedOfferAnswerInputMixin",
    "RequireRecordedOfferAnswerNode",
    "UnrecordedOfferAnswerError",
    "recorded_invitee",
    "recorded_offer_answer_key",
    "recorded_recommendation",
]
