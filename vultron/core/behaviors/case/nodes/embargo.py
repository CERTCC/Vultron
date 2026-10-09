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

"""
Embargo management action nodes and helpers for case behavior trees.

Provides action nodes for initializing the embargo a case is created with.
Eligibility and duration resolution live in the sibling
``embargo_resolution.py``; selecting a contested creation's pending revision
lives in ``embargo_revision.py``.

The composite subtree assembling these leaf nodes is defined in the sibling
``embargo_tree.py`` module at the process-area root per BTND-07-003:

- ``InitializeDefaultEmbargoNode``

Per specs/case-management.yaml CM-02, OX-03-001 and
notes/protocol-event-cascades.md D5-6-EMBARGORCP.
"""

import logging
import uuid

import isodate  # type: ignore[import-untyped]
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.embargo_revision import (
    CANDIDATE_KEY,
    CreationTimeRevisionCandidate,
    creation_revision_parties,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models._helpers import _as_id, from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.services.embargo_duration import (
    EmbargoDurationSource,
    InitialEmbargoDuration,
)
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.services.embargo_lifecycle.creation import (
    CreationRevision,
)
from vultron.errors import VultronError

logger = logging.getLogger(__name__)


#: Appended to the case id to name the creation-time embargo's uuid5.
_CREATION_TIME_EMBARGO_SUFFIX = "#creation-time-embargo"


def creation_time_embargo_id(case_id: str) -> str:
    """Return the id of the creation-time embargo minted for *case_id*.

    The id is derived from the case, so every attempt to initialize the same
    case names the same event (EP-04-012).
    """
    name = f"{case_id}{_CREATION_TIME_EMBARGO_SUFFIX}"
    return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, name)}"


class CreateEmbargoEventNode(DataLayerActionWithPorts):
    """Build the creation-time embargo event and publish it to the blackboard.

    Its duration is the ``InitialEmbargoDuration`` that
    ``ResolveEmbargoDurationNode`` resolved (EP-04-005 through EP-04-007).
    When the sender's proposal won, the event is the sender's own
    ``EmbargoEvent`` with its ``context`` rewritten from the report to the
    case — the same terms and identity the Reporter stated, now about the case
    (EP-04-004, EP-04-009).  Otherwise an event is minted for the resolved
    duration under ``creation_time_embargo_id(case_id)``.

    The node writes nothing.  ``InitializeCreationEmbargoNode`` stores the
    event in the commit that activates it (EP-04-002), so an attempt that
    stops first leaves no event behind, and a redelivery that resolves to the
    other branch cannot orphan it (EP-04-012, #4182).
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=True),
        "initial_embargo_duration": PortInformation(
            data_type=InitialEmbargoDuration, required=True
        ),
        "sender_proposed_embargo": PortInformation(
            data_type=object, required=False
        ),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "default_embargo": PortInformation(
            data_type=EmbargoEvent, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "initial_embargo_duration": "/initial_embargo_duration",
            "sender_proposed_embargo": "/sender_proposed_embargo",
            "default_embargo": "/default_embargo",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")
        self.initial_embargo_duration_bb: InitialEmbargoDuration = (
            self.get_input("initial_embargo_duration")
        )

    def update(self) -> Status:
        case_id = self.case_id_bb
        if not isinstance(case_id, str):
            self.logger.error("%s: case_id not found in blackboard", self.name)
            return Status.FAILURE

        resolved = self.initial_embargo_duration_bb
        duration = resolved.duration
        sender_event = self._try_get_input("sender_proposed_embargo")
        if (
            resolved.source is EmbargoDurationSource.SENDER_PROPOSAL
            and isinstance(sender_event, EmbargoEvent)
        ):
            # The Reporter's terms carry over whole; only the subject changes
            # from the report to the case (EP-04-004).
            embargo = sender_event.with_subject(case_id)
        else:
            embargo = EmbargoEvent(
                id_=creation_time_embargo_id(case_id),
                end_time=from_now_utc(duration),
                context=case_id,
            )

        self._set_output("default_embargo", embargo)
        self.logger.info(
            "Built embargo '%s' for case '%s'"
            " (end_time: %s, duration: %s, source: %s)",
            embargo.id_,
            case_id,
            embargo.end_time.isoformat(),
            isodate.duration_isoformat(duration),
            resolved.source.value,
        )
        return Status.SUCCESS


class InitializeCreationEmbargoNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Take the case's creation-time embargo from ``EM.NONE`` to ``EM.ACTIVE``.

    One commit: ``EmbargoLifecycle.initialize_creation_embargo`` applies the
    PROPOSE and ACCEPT triggers together, attaches the embargo as
    ``active_embargo``, records consent, seeds the case owner as a signatory
    (CM-14-003), stores the ``EmbargoEvent`` ``CreateEmbargoEventNode`` built
    (no earlier node writes it, #4182) and registers the revision
    ``ResolveCreationTimeRevisionNode`` selected (``ACTIVE → REVISE``,
    EP-04-003), all in one ``save_many``, so
    ``EM.PROPOSED`` is never persisted (EP-04-002).  Any failure leaves the
    case at ``EM.NONE`` with nothing written, which the once-per-case guard
    lets a redelivered proposal finish (EP-04-012).  Proposing and then
    activating in two nodes saved the case at ``PROPOSED`` in between (#4123);
    seeding and registering in nodes after the activation could leave an
    ``ACTIVE`` case unseeded or with its revision missing (#4142).

    The revision is proposed by the party whose terms lost: the reporter of
    *report_id* or the case owner (``creation_revision_parties``), so that
    party's consent record, not the executing actor's, gains it (MSM-07-005,
    #4152).  A contest with no resolvable reporter fails before the
    initialization commit, leaving the case at ``EM.NONE``.

    A registered revision owes a relay (EP-04-011): the same commit stores a
    :class:`PendingCreationTimeRevisionRelay` naming the loser, the report,
    this CASE_MANAGER and a freshly minted id for its ``Invite``, which
    ``RelayCreationTimeRevisionNode`` reads from the store.  Committing both
    together means no failure leaves a registered revision with no relay
    owed, nor a relay owed for a revision never registered (#4121, #4156).

    The transition itself is validated by the lifecycle service, not by an
    upstream guard (CSB-16, EMB-18-001).  The once-per-case guard ahead of
    this node takes every case past ``EM.NONE``, so a case that reaches it
    with an embargo already attached is inconsistent: the service refuses
    it and the node fails, rather than report an initialization it did not
    make (ARCH-15).

    Args:
        report_id: The report whose author proposed the sender's terms; only
            read when a revision was selected.
        name: Optional node name.
    """

    def __init__(
        self, report_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=True),
        "default_embargo": PortInformation(
            data_type=EmbargoEvent, required=True
        ),
        CANDIDATE_KEY: PortInformation(
            data_type=CreationTimeRevisionCandidate | None, required=False
        ),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "default_embargo_initialized": PortInformation(
            data_type=object, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            key: f"/{key}"
            for key in (
                "case_id",
                "default_embargo",
                "default_embargo_initialized",
                CANDIDATE_KEY,
            )
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")
        self.default_embargo_bb: EmbargoEvent = self.get_input(
            "default_embargo"
        )

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case_id = self.case_id_bb
        embargo = self.default_embargo_bb
        if not isinstance(case_id, str) or not isinstance(
            embargo, EmbargoEvent
        ):
            self.logger.error(
                "%s: case_id/default_embargo not found in blackboard",
                self.name,
            )
            return Status.FAILURE

        stored_case, failure = self._require_case(case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        # The creation-time embargo is the owner's to set: either the owner
        # creates the case itself, or the CASE_MANAGER creates it on the
        # owner's behalf from a proposal (CP-09-001, CP-09-003) — the case is
        # then attributed to the owner while the CASE_MANAGER runs this tree.
        owner_actor_id = _as_id(stored_case.attributed_to)
        if self.actor_id != owner_actor_id and self.actor_id != (
            resolve_case_manager_id(stored_case, self.datalayer)
        ):
            self.feedback_message = (
                f"actor '{self.actor_id}' is neither case owner"
                f" '{owner_actor_id}' nor the CASE_MANAGER of case '{case_id}'"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        candidate = self._try_get_input(CANDIDATE_KEY)
        if candidate is not None and not isinstance(
            candidate, CreationTimeRevisionCandidate
        ):
            self.feedback_message = (
                f"{self.name}: {CANDIDATE_KEY} is a"
                f" {type(candidate).__name__}, not a revision candidate"
            )
            self.logger.error("%s", self.feedback_message)
            return Status.FAILURE

        try:
            revision = (
                None
                if candidate is None
                else self._revision(stored_case, candidate)
            )
            EmbargoLifecycle(
                persistence=self.datalayer
            ).initialize_creation_embargo(
                case_id=case_id,
                embargo=embargo,
                actor_id=self.actor_id,
                revision=revision,
            )
        except VultronError as exc:
            self.feedback_message = (
                f"{self.name}: failed to initialize embargo '{embargo.id_}'"
                f" for case '{case_id}': {exc}"
            )
            self.logger.error("%s", self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
            return Status.FAILURE

        self._set_output("default_embargo_initialized", True)
        return Status.SUCCESS

    def _revision(
        self, case: VulnerabilityCase, candidate: CreationTimeRevisionCandidate
    ) -> CreationRevision:
        """Name the revision's proposer and the relay it owes (EP-04-011)."""
        assert self.datalayer is not None
        assert self.actor_id is not None
        proposer_id, _winner = creation_revision_parties(
            self.datalayer, case, candidate.losing_source, self._report_id
        )
        # creation_revision_parties refuses a missing report id.
        assert self._report_id is not None
        return CreationRevision(
            embargo=candidate.embargo,
            proposer_id=proposer_id,
            relay=candidate.relay_obligation(
                case.id_, self._report_id, self.actor_id
            ),
        )
