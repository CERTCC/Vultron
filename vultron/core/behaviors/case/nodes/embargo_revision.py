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

"""Register the losing side of shortest-wins as a pending revision (EP-04-003).

When both the sender and the case owner carried a proposal at case creation,
``ResolveEmbargoDurationNode`` made the shorter one active.  EP-04-003 says the
longer SHOULD be registered as a pending revision, so the party that wanted
more can negotiate the contested tail inside the agreed embargo rather than
losing it outright (ADR-0096).  ``RegisterLongerProposalAsRevisionNode`` is
the last leaf of ``InitializeDefaultEmbargoNode``; it does nothing when there
was no contest.

The revision then follows the relay like any other (EP-04-011, ADR-0113): the
registration mints the id its ``Invite`` will carry and records the relay as
owed in a durable ``PendingCreationTimeRevisionRelay`` *before* it registers
anything, so no crash can leave a registered revision that nobody owes.
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

from vultron.core.behaviors.case.nodes.embargo import (
    persist_creation_time_embargo,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models._helpers import _new_urn, from_now_utc
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.pending_creation_time_revision_relay import (
    LosingSource,
    PendingCreationTimeRevisionRelay,
)
from vultron.core.services.embargo_duration import (
    EmbargoDurationSource,
    InitialEmbargoDuration,
)
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.errors import BtNodePreconditionError, VultronError

logger = logging.getLogger(__name__)


class RegisterLongerProposalAsRevisionNode(DataLayerActionWithPorts):
    """Propose the longer of the two creation-time candidates as a revision.

    Reads what ``ResolveEmbargoDurationNode`` published.  Exactly one of two
    contests can have happened:

    - the **sender's** proposal won and the owner's actor default was longer:
      a fresh ``EmbargoEvent`` for the actor default is created on the case;
    - the **actor default** won and the sender's proposal was longer: the
      sender's own ``EmbargoEvent`` is registered, its ``context`` rewritten
      to the case (EP-04-004, EP-04-009).

    Either way ``EmbargoLifecycle.propose_embargo`` drives ``ACTIVE → REVISE``
    (EMB-18-001); a proposal changes no participant's consent (ADR-0093).  A
    tie, a protocol-default outcome, or a lone candidate registers nothing.

    Before registering, the node records the relay as owed: a
    :class:`PendingCreationTimeRevisionRelay` keyed on the case, carrying the
    loser, a freshly minted id for its ``Invite``, the report the reporter is
    resolved from, and the CASE_MANAGER that owes the relay (EP-04-011).  The
    record comes first because the registration is the effect it obliges: a
    crash after it leaves a record whose revision never opened, which the
    relay discharges unsent, never an open revision with no record.  A
    contest with no report to resolve the reporter from raises before either
    write, since no relay could ever be sent for it (#4156).
    """

    def __init__(
        self, report_id: str | None = None, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._report_id = report_id

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

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            key: f"/{key}"
            for key in (
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
                # missing: registering nothing here would report SUCCESS for a
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
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

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
            if loser is None:
                return Status.SUCCESS
            # EP-04-011: the relay is owed before the revision exists (#4156).
            self.datalayer.save(
                self._relay_obligation(case_id, loser.id_, resolved)
            )
            # ``propose_embargo`` requires the event to exist first; should the
            # proposal then be refused, the stored event is an orphan the
            # FAILURE below names, not a silent leftover.  A stored twin under
            # the sender's id that is not this embargo is refused outright.
            persist_creation_time_embargo(self.datalayer, loser, case_id)
            result = EmbargoLifecycle(
                persistence=self.datalayer
            ).propose_embargo(
                case_id=case_id,
                embargo_id=loser.id_,
                actor_id=self.actor_id,
            )
        except VultronError as exc:
            self.feedback_message = (
                f"{self.name}: could not register the longer proposal as a"
                f" revision on case '{case_id}': {exc}"
            )
            self.logger.error("%s", self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
            return Status.FAILURE

        self.logger.info(
            "Registered the longer creation-time proposal '%s' as a pending"
            " revision on case '%s' (EM %s → %s; active terms came from %s;"
            " EP-04-003)",
            loser.id_,
            case_id,
            result.em_before,
            result.em_after,
            resolved.source.value,
        )
        return Status.SUCCESS

    def _relay_obligation(
        self, case_id: str, embargo_id: str, resolved: InitialEmbargoDuration
    ) -> PendingCreationTimeRevisionRelay:
        """Name the revision, its future Invite's id, and who owes the relay."""
        assert self.actor_id is not None
        if not self._report_id:
            raise RuntimeError(
                f"{self.name}: creation-time revision '{embargo_id}' on case"
                f" '{case_id}' has no report, so the reporter it is relayed to"
                " or for cannot be resolved (EP-04-011)"
            )
        losing_source = (
            EmbargoDurationSource.ACTOR_DEFAULT
            if resolved.source is EmbargoDurationSource.SENDER_PROPOSAL
            else EmbargoDurationSource.SENDER_PROPOSAL
        )
        return PendingCreationTimeRevisionRelay(
            case_id=case_id,
            embargo_id=embargo_id,
            proposal_id=_new_urn(),
            losing_source=cast(LosingSource, losing_source.value),
            report_id=self._report_id,
            case_actor_id=self.actor_id,
        )
