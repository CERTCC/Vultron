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

"""Select the losing side of shortest-wins as a pending revision (EP-04-003).

When both the sender and the case owner carried a proposal at case creation,
``ResolveEmbargoDurationNode`` made the shorter one active.  EP-04-003 says the
longer SHOULD be registered as a pending revision, so the party that wanted
more can negotiate the contested tail inside the agreed embargo rather than
losing it outright (ADR-0096).  ``ResolveCreationTimeRevisionNode`` picks that
longer proposal before anything is written and publishes it as
``creation_time_revision_candidate``; ``InitializeCreationEmbargoNode``
registers it in the same commit that activates the embargo, so a failure can
never leave the case active with the revision missing (EP-04-012, #4142).

The revision then follows the relay like any other (EP-04-011, ADR-0113): the
same commit records the relay as owed in a durable
``PendingCreationTimeRevisionRelay`` that mints the id its ``Invite`` will
carry, so no crash can leave a registered revision that nobody owes.
``RelayCreationTimeRevisionNode`` (``embargo_revision_relay``) emits that
``Invite`` on the losing party's behalf, and indexes it for the owner's default
selection (EP-08-002), only once the initialization sequence is complete
(CM-14-007).  A failed relay keeps the record, so redelivery or the startup
runner retries it (#4121, #4156).
"""

import logging
from datetime import timedelta
from typing import cast

from py_trees.common import Status
from pydantic import BaseModel, ConfigDict

from vultron.core.behaviors.case.report_author import report_author_id
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models._helpers import _as_id, _new_urn, from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.pending_creation_time_revision_relay import (
    LosingSource,
    PendingCreationTimeRevisionRelay,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_duration import (
    EmbargoDurationSource,
    InitialEmbargoDuration,
)
from vultron.errors import BtNodePreconditionError

logger = logging.getLogger(__name__)

CANDIDATE_KEY = "creation_time_revision_candidate"


def creation_revision_parties(
    dl: CasePersistence,
    case: VulnerabilityCase,
    losing_source: EmbargoDurationSource,
    report_id: str | None,
) -> tuple[str, str]:
    """Return ``(proposer, winner)`` for *case*'s creation-time revision.

    The two parties are the case owner and the reporter of *report_id*, whose
    terms arrived as the sender proposal (EP-04-004).  The party whose terms
    lost shortest-wins proposed the revision (``losing_source``): the reporter
    for ``SENDER_PROPOSAL``, the owner for ``ACTOR_DEFAULT``.  The proposer's
    consent record gains the revision (MSM-07-005, #4152) and the relay is
    attributed to it (EP-04-011), so both read it here.

    Raises:
        BtNodePreconditionError: If *case* names no owner, *report_id* is
            missing, or the report names no author.
        VultronNotFoundError: If no report is stored under *report_id*.
    """
    owner_id = _as_id(case.attributed_to)
    if not owner_id:
        raise BtNodePreconditionError(
            f"case '{case.id_}' names no CASE_OWNER (CP-09-001)"
        )
    if not report_id:
        raise BtNodePreconditionError(
            "no report id, so the reporter cannot be resolved"
        )
    reporter_id = report_author_id(dl, report_id)
    if losing_source is EmbargoDurationSource.SENDER_PROPOSAL:
        return reporter_id, owner_id
    return owner_id, reporter_id


class CreationTimeRevisionCandidate(BaseModel):
    """The longer creation-time proposal, selected but not yet registered.

    ``embargo`` is the ``EmbargoEvent`` to store and propose; ``losing_source``
    names whose terms lost shortest-wins and so who the proposer is: the
    reporter for ``SENDER_PROPOSAL``, the case owner for ``ACTOR_DEFAULT``.
    """

    model_config = ConfigDict(frozen=True)

    embargo: EmbargoEvent
    losing_source: EmbargoDurationSource

    def relay_obligation(
        self, case_id: str, report_id: str, case_actor_id: str
    ) -> PendingCreationTimeRevisionRelay:
        """Record the relay this revision owes, minting its Invite's id.

        The relay records that id in ``pending_embargo_proposal_index`` once
        the Invite is sent, not here: the bootstrap
        ``Create(VulnerabilityCase)`` carries the case whole, and an index
        entry already in it would read, at the invitee, as an Invite it had
        already answered (EP-04-011).
        """
        return PendingCreationTimeRevisionRelay(
            case_id=case_id,
            embargo_id=self.embargo.id_,
            proposal_id=_new_urn(),
            losing_source=cast(LosingSource, self.losing_source.value),
            report_id=report_id,
            case_actor_id=case_actor_id,
        )


class ResolveCreationTimeRevisionNode(DataLayerActionWithPorts):
    """Select the longer of the two creation-time candidates as a revision.

    Reads what ``ResolveEmbargoDurationNode`` published.  Exactly one of two
    contests can have happened:

    - the **sender's** proposal won and the owner's actor default was longer:
      a fresh ``EmbargoEvent`` for the actor default is the candidate;
    - the **actor default** won and the sender's proposal was longer: the
      sender's own ``EmbargoEvent`` is, its ``context`` rewritten to the case
      (EP-04-004, EP-04-009).

    A tie, a protocol-default outcome, or a lone candidate selects nothing.
    The node writes nothing to the store: ``InitializeCreationEmbargoNode``
    stores and proposes the candidate in the commit that activates the
    embargo (EP-04-002, EP-04-012).  The output is written (``None`` when
    there is no contest) whenever this node ticks, and ``BTBridge`` scopes it
    to one execution, so no later execution reads it (BT-17-003).
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=True),
        "initial_embargo_duration": PortInformation(
            data_type=InitialEmbargoDuration, required=True
        ),
        "actor_default_embargo_duration": PortInformation(
            data_type=object, required=True
        ),
        "sender_proposed_embargo_duration": PortInformation(
            data_type=object, required=False
        ),
        "sender_proposed_embargo": PortInformation(
            data_type=object, required=False
        ),
    }

    OUTPUT_PORTS: dict[str, PortInformation] = {
        CANDIDATE_KEY: PortInformation(
            data_type=CreationTimeRevisionCandidate | None, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            key: f"/{key}"
            for key in (
                CANDIDATE_KEY,
                "case_id",
                "initial_embargo_duration",
                "actor_default_embargo_duration",
                "sender_proposed_embargo_duration",
                "sender_proposed_embargo",
            )
        }

    def _losing_candidate(
        self, case_id: str, resolved: InitialEmbargoDuration
    ) -> EmbargoEvent | None:
        """Return the ``EmbargoEvent`` to register, or ``None`` if no contest."""
        actor_default = self._try_get_input("actor_default_embargo_duration")
        sender_duration = self._try_get_input(
            "sender_proposed_embargo_duration"
        )
        sender_event = self._try_get_input("sender_proposed_embargo")

        if resolved.source is EmbargoDurationSource.SENDER_PROPOSAL:
            if (
                isinstance(actor_default, timedelta)
                and actor_default > resolved.duration
            ):
                return EmbargoEvent(
                    context=case_id, end_time=from_now_utc(actor_default)
                )
            return None
        if resolved.source is EmbargoDurationSource.ACTOR_DEFAULT:
            if (
                not isinstance(sender_duration, timedelta)
                or sender_duration <= resolved.duration
            ):
                return None
            if not isinstance(sender_event, EmbargoEvent):
                # The duration was compared but the event it was read from is
                # missing: selecting nothing here would report SUCCESS for a
                # revision that never happened (BT-HELPER-01).
                raise BtNodePreconditionError(
                    f"{self.name}: sender_proposed_embargo_duration is on the"
                    " blackboard but sender_proposed_embargo is not; the"
                    " losing proposal cannot be registered (EP-04-003)"
                )
            # The sender's terms, now about the case (EP-04-004).
            return sender_event.with_subject(case_id)
        return None

    def update(self) -> Status:
        self._set_output(CANDIDATE_KEY, None)
        case_id = self._try_get_input("case_id")
        resolved = self._try_get_input("initial_embargo_duration")
        if not isinstance(case_id, str) or not isinstance(
            resolved, InitialEmbargoDuration
        ):
            self.feedback_message = (
                f"{self.name}: case_id or initial_embargo_duration missing"
                " from the blackboard"
            )
            self.logger.error("%s", self.feedback_message)
            return Status.FAILURE

        try:
            loser = self._losing_candidate(case_id, resolved)
        except BtNodePreconditionError as exc:
            self.feedback_message = str(exc)
            self.logger.error("%s", self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
            return Status.FAILURE
        if loser is None:
            return Status.SUCCESS

        losing_source = (
            EmbargoDurationSource.ACTOR_DEFAULT
            if resolved.source is EmbargoDurationSource.SENDER_PROPOSAL
            else EmbargoDurationSource.SENDER_PROPOSAL
        )
        self.logger.info(
            "Selected the longer creation-time proposal '%s' (from %s) as the"
            " pending revision for case '%s'; active terms came from %s"
            " (EP-04-003)",
            loser.id_,
            losing_source.value,
            case_id,
            resolved.source.value,
        )
        self._set_output(
            CANDIDATE_KEY,
            CreationTimeRevisionCandidate(
                embargo=loser, losing_source=losing_source
            ),
        )
        return Status.SUCCESS
