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
    REVISION_KEY,
    CreationTimeRevision,
    CreationTimeRevisionCandidate,
    creation_revision_parties,
)
from vultron.core.behaviors.embargo.nodes.em_state import read_case_em_state
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
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
    persist_creation_time_embargo,
)
from vultron.core.states.em import EM
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
    """Create the initial embargo event and publish embargo_id to blackboard.

    Its duration is the ``InitialEmbargoDuration`` that
    ``ResolveEmbargoDurationNode`` resolved (EP-04-005 through EP-04-007).
    When the sender's proposal won, the event is the sender's own
    ``EmbargoEvent`` with its ``context`` rewritten from the report to the
    case — the same terms and identity the Reporter stated, now about the case
    (EP-04-004, EP-04-009).  Otherwise an event is minted for the resolved
    duration under ``creation_time_embargo_id(case_id)``, so a rerun on a
    half-built case reuses the first attempt's event instead of storing a
    second one beside it (EP-04-012, #4117).
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
        "default_embargo_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            "initial_embargo_duration": "/initial_embargo_duration",
            "sender_proposed_embargo": "/sender_proposed_embargo",
            "default_embargo_id": "/default_embargo_id",
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")
        self.initial_embargo_duration_bb: InitialEmbargoDuration = (
            self.get_input("initial_embargo_duration")
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
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
            end_time = embargo.end_time
            minted = False
        else:
            minted = True
            end_time = from_now_utc(duration)
            embargo = EmbargoEvent(
                id_=creation_time_embargo_id(case_id),
                end_time=end_time,
                context=case_id,
            )
        try:
            # Only a minted event is ours to re-stamp: a stored twin of the
            # sender's event must still match it (persist_*, EP-04-004).
            if not (
                minted and self._restamp_half_built_attempt(embargo, case_id)
            ):
                persist_creation_time_embargo(self.datalayer, embargo, case_id)
        except VultronError as exc:
            self.feedback_message = f"{self.name}: {exc}"
            self.logger.error("%s", self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
            return Status.FAILURE

        self._set_output("default_embargo_id", embargo.id_)
        self.logger.info(
            "Initialized embargo '%s' for case '%s'"
            " (end_time: %s, duration: %s, source: %s)",
            embargo.id_,
            case_id,
            end_time.isoformat(),
            isodate.duration_isoformat(duration),
            resolved.source.value,
        )
        return Status.SUCCESS

    def _restamp_half_built_attempt(
        self, embargo: EmbargoEvent, case_id: str
    ) -> bool:
        """Overwrite an earlier attempt's minted event with *embargo*.

        A minted event carries ``creation_time_embargo_id(case_id)``, so a
        rerun on a half-built case (left at ``EM.NONE`` with the event
        stored — EP-04-012 admits it) finds the first attempt's event under
        the same id.  Nothing references it: the case is still at ``NONE``,
        so no proposal, consent record or ledger entry names it.  It is
        replaced in place with the terms this run resolved, so its window is
        measured from the run that activates it and no second, orphan event is
        stored beside it (#4117).  Returns ``False`` when no such event is
        stored; an object under the id that is not this case's embargo is left
        to ``persist_creation_time_embargo``, which refuses it.

        "Nothing references it" is checked here, not inherited from the
        upstream guard (CSB-16): the case must be at ``EM.NONE`` with no
        active embargo and must not list the id as a proposal.  Otherwise
        ``False`` is returned and ``persist_creation_time_embargo`` refuses
        the changed terms rather than rewriting an event already in use
        (#4123).
        """
        assert self.datalayer is not None  # update() checked it
        stored = self.datalayer.read(embargo.id_)
        if not isinstance(stored, EmbargoEvent) or stored.context != case_id:
            return False
        if not self._unreferenced_by_case(embargo.id_, case_id):
            return False
        self.datalayer.save(embargo)
        self.logger.info(
            "Actor '%s' re-stamped creation-time embargo '%s' for case '%s',"
            " left at EM.NONE by an earlier attempt (end_time %s -> %s;"
            " EP-04-012)",
            self.actor_id,
            embargo.id_,
            case_id,
            stored.end_time.isoformat(),
            embargo.end_time.isoformat(),
        )
        return True

    def _unreferenced_by_case(self, embargo_id: str, case_id: str) -> bool:
        """Return whether case *case_id* is half-built and names no embargo.

        Raises:
            BtNodePreconditionError: when the case or its EM state cannot be
                read; ``update()`` turns it into FAILURE.
        """
        assert self.datalayer is not None  # update() checked it
        if read_case_em_state(self.datalayer, case_id) is not EM.NONE:
            return False
        case = self.datalayer.read(case_id)
        if not isinstance(case, VulnerabilityCase):
            return False
        return (
            _as_id(case.active_embargo) is None
            and embargo_id not in case.proposed_embargo_ids
        )


class InitializeCreationEmbargoNode(DataLayerActionWithPorts):
    """Take the case's creation-time embargo from ``EM.NONE`` to ``EM.ACTIVE``.

    One commit: ``EmbargoLifecycle.initialize_creation_embargo`` applies the
    PROPOSE and ACCEPT triggers together, attaches the embargo as
    ``active_embargo``, records consent, seeds the case owner ``SIGNATORY``
    (CM-14-003) and registers the revision ``ResolveCreationTimeRevisionNode``
    selected (``ACTIVE → REVISE``, EP-04-003), all in one ``save_many``, so
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

    A registered revision is published, under a freshly minted proposal id,
    as ``creation_time_revision`` for ``RelayCreationTimeRevisionNode``
    (EP-04-011).  The key is written (``None``) first whenever this node
    ticks, and ``BTBridge`` scopes it to one execution (BT-17-003).

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
        "default_embargo_id": PortInformation(data_type=str, required=True),
        CANDIDATE_KEY: PortInformation(
            data_type=CreationTimeRevisionCandidate | None, required=False
        ),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        "default_embargo_initialized": PortInformation(
            data_type=object, required=True
        ),
        REVISION_KEY: PortInformation(
            data_type=CreationTimeRevision | None, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            key: f"/{key}"
            for key in (
                "case_id",
                "default_embargo_id",
                "default_embargo_initialized",
                CANDIDATE_KEY,
                REVISION_KEY,
            )
        }

    def initialise(self) -> None:
        super().initialise()
        self.case_id_bb: str = self.get_input("case_id")
        self.default_embargo_id_bb: str = self.get_input("default_embargo_id")

    def update(self) -> Status:
        self._set_output(REVISION_KEY, None)
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case_id = self.case_id_bb
        embargo_id = self.default_embargo_id_bb
        if not isinstance(case_id, str) or not isinstance(embargo_id, str):
            self.logger.error(
                "%s: case_id/default_embargo_id not found in blackboard",
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
                else CreationRevision(
                    embargo=candidate.embargo,
                    proposer_id=creation_revision_parties(
                        self.datalayer,
                        stored_case,
                        candidate.losing_source,
                        self._report_id,
                    )[0],
                )
            )
            EmbargoLifecycle(
                persistence=self.datalayer
            ).initialize_creation_embargo(
                case_id=case_id,
                embargo_id=embargo_id,
                actor_id=self.actor_id,
                revision=revision,
            )
        except VultronError as exc:
            self.feedback_message = (
                f"{self.name}: failed to initialize embargo '{embargo_id}'"
                f" for case '{case_id}': {exc}"
            )
            self.logger.error("%s", self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
            return Status.FAILURE

        self._set_output("default_embargo_initialized", True)
        if candidate is not None:
            self._set_output(REVISION_KEY, candidate.registered(case_id))
        return Status.SUCCESS
