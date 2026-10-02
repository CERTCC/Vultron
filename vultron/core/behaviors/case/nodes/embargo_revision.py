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
registration indexes it under the id its ``Invite`` will carry, so the owner's
default selection reaches it at once (EP-08-002), and
``RelayCreationTimeRevisionNode`` emits that ``Invite`` on the losing party's
behalf only once the initialization sequence is complete (CM-14-007).
"""

import logging
from datetime import timedelta

from py_trees.common import Status
from pydantic import BaseModel, ConfigDict

from vultron.core.behaviors.case.nodes.embargo import (
    persist_creation_time_embargo,
)
from vultron.core.behaviors.case.report_author import report_author_id
from vultron.core.behaviors.embargo.nodes.relay import (
    RelayEmbargoInviteToEachNode,
)
from vultron.core.behaviors.embargo.proposal_index import (
    record_embargo_proposal_index,
)
from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    PortInformation,
)
from vultron.core.models._helpers import _as_id, _new_urn, from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.participants.recipients import invitation_recipients
from vultron.core.services.embargo_duration import (
    EmbargoDurationSource,
    InitialEmbargoDuration,
)
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.errors import BtNodePreconditionError, VultronError
from vultron.primitives import NonEmptyString

logger = logging.getLogger(__name__)

_REVISION_KEY = "creation_time_revision"


class CreationTimeRevision(BaseModel):
    """The creation-time revision the registration indexed, for its relay.

    ``proposal_id`` is the id the relayed ``Invite`` will carry, recorded in
    ``pending_embargo_proposal_index`` before that Invite exists (EP-04-011).
    ``losing_source`` names whose terms lost shortest-wins and so who the
    proposer is: the reporter for ``SENDER_PROPOSAL``, the case owner for
    ``ACTOR_DEFAULT``.
    """

    model_config = ConfigDict(frozen=True)

    case_id: NonEmptyString
    embargo_id: NonEmptyString
    proposal_id: NonEmptyString
    losing_source: EmbargoDurationSource


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

    A registered revision is indexed under a freshly minted proposal id and
    published as ``creation_time_revision`` for
    :class:`RelayCreationTimeRevisionNode` (EP-04-011).  The key is written
    (``None``) first whenever this node ticks, and ``BTBridge`` scopes it to
    one execution, so the relay never reads a revision an earlier execution
    left on the process-global blackboard (BT-17-003).
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
        _REVISION_KEY: PortInformation(
            data_type=CreationTimeRevision | None, required=True
        ),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            key: f"/{key}"
            for key in (
                _REVISION_KEY,
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
        self._set_output(_REVISION_KEY, None)
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
            revision = self._index_revision(case_id, loser.id_, resolved)
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
        self._set_output(_REVISION_KEY, revision)
        return Status.SUCCESS

    def _index_revision(
        self, case_id: str, embargo_id: str, resolved: InitialEmbargoDuration
    ) -> CreationTimeRevision:
        """Index the revision under its future Invite's id (EP-04-011, EP-08-002)."""
        assert self.datalayer is not None
        proposal_id = _new_urn()
        record_embargo_proposal_index(
            self.datalayer, case_id, embargo_id, proposal_id
        )
        return CreationTimeRevision(
            case_id=case_id,
            embargo_id=embargo_id,
            proposal_id=proposal_id,
            losing_source=(
                EmbargoDurationSource.ACTOR_DEFAULT
                if resolved.source is EmbargoDurationSource.SENDER_PROPOSAL
                else EmbargoDurationSource.SENDER_PROPOSAL
            ),
        )


class RelayCreationTimeRevisionNode(RelayEmbargoInviteToEachNode):
    """Relay the creation-time revision to the party whose terms won (EP-04-011).

    The #3913 relay emit, fed from what ``RegisterLongerProposalAsRevisionNode``
    published rather than from a received proposal: the CASE_MANAGER emits
    ``Invite(EmbargoEvent)`` as ``actor`` with the losing party in
    ``attributedTo`` (CM-24-001, CM-24-002), under the proposal id the
    registration already indexed, and commits it in this tree.  The losing
    party is the proposer and is not invited (EP-09-002).  The case tree places
    this node after its ledger commit, so no modification is initiated before
    the initialization sequence is complete (CM-14-007).

    Nothing is relayed, and the node succeeds, when no revision was registered
    in this execution (no contest, a tie, or a case already initialized), when
    the published revision names another case, when it is no longer open, or
    when its Invite is already in the ledger.  The last two are read from the
    store, not the blackboard.  A revision whose parties cannot be resolved, or
    whose winning party is not an invitation recipient, is a FAILURE; a
    reporter that is itself the CASE_OWNER has nobody to invite.  A failed
    relay is not retried by a redelivery, which never reaches the registration
    (#4121).
    """

    def __init__(self, report_id: str | None, name: str | None = None) -> None:
        super().__init__(
            case_id="",
            embargo_id="",
            proposer_id="",
            name=name or self.__class__.__name__,
        )
        self._report_id = report_id
        self._revision: CreationTimeRevision | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
        _REVISION_KEY: PortInformation(
            data_type=CreationTimeRevision | None, required=False
        ),
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            "case_id": "/case_id",
            _REVISION_KEY: f"/{_REVISION_KEY}",
            "sync_port": "/sync_port",
        }

    def _load_relay_inputs(self) -> None:
        self._recipients = []
        revision = self._try_get_input(_REVISION_KEY)
        current_case_id = self._try_get_input("case_id")
        self._revision = (
            revision
            if isinstance(revision, CreationTimeRevision)
            and revision.case_id == current_case_id
            else None
        )
        if self._revision is not None:
            self._case_id = self._revision.case_id
            self._embargo_id = self._revision.embargo_id

    def _activity_id_for(self, recipient_id: str) -> str | None:
        return self._revision.proposal_id if self._revision else None

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        if self._revision is None:
            self.feedback_message = "no creation-time revision to relay"
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)
        if not self._still_to_relay(case, self._revision):
            return Status.SUCCESS
        try:
            self._resolve_parties(case, self._revision)
        except VultronError as exc:
            self.feedback_message = (
                f"{self.name}: cannot relay creation-time revision"
                f" '{self._embargo_id}' on case '{self._case_id}': {exc}"
            )
            self.logger.error("%s", self.feedback_message)  # noqa: TRY400  # ruff-baseline #3353
            return Status.FAILURE
        return super().update()

    def _still_to_relay(
        self, case: VulnerabilityCase, revision: CreationTimeRevision
    ) -> bool:
        """True while the revision is open and its Invite is not yet committed."""
        assert self.datalayer is not None
        indexed = case.pending_embargo_proposal_index.get(revision.embargo_id)
        if indexed != revision.proposal_id:
            reason = "is no longer an open proposal"
        elif any(
            entry.log_object_id == revision.proposal_id
            for entry in recorded_entries_for_case(
                case_id=case.id_, dl=self.datalayer
            )
        ):
            reason = "was already relayed"
        else:
            return True
        self.feedback_message = (
            f"creation-time revision '{revision.embargo_id}' on case"
            f" '{case.id_}' {reason} — nothing to relay"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return False

    def _resolve_parties(
        self, case: VulnerabilityCase, revision: CreationTimeRevision
    ) -> None:
        """Set the proposer (the loser) and the one invitee (the winner)."""
        assert self.datalayer is not None
        assert self.actor_id is not None
        owner_id = _as_id(case.attributed_to)
        if not owner_id:
            raise BtNodePreconditionError(
                f"case '{case.id_}' names no CASE_OWNER (CP-09-001)"
            )
        if not self._report_id:
            raise BtNodePreconditionError(
                "no report id, so the reporter cannot be resolved"
            )
        # The reporter's terms arrived as the sender proposal (EP-04-004).
        reporter_id = report_author_id(self.datalayer, self._report_id)
        if revision.losing_source is EmbargoDurationSource.SENDER_PROPOSAL:
            self._proposer_id, winner_id = reporter_id, owner_id
        else:
            self._proposer_id, winner_id = owner_id, reporter_id
        # Shared recipient selection (CM-10-007), narrowed to the other party:
        # nobody else held terms at creation (EP-04-011).
        self._recipients = [
            actor_id
            for actor_id in invitation_recipients(
                case,
                self.datalayer,
                excluding={self.actor_id, self._proposer_id},
            )
            if actor_id == winner_id
        ]
        if not self._recipients and winner_id == self._proposer_id:
            # The owner reported to itself: one party held both sets of terms,
            # so there is nobody else to invite.
            self.logger.info(
                "%s: '%s' is both reporter and CASE_OWNER — no other party to"
                " relay revision '%s' to",
                self.name,
                winner_id,
                revision.embargo_id,
            )
            return
        if not self._recipients:
            # EP-04-011 says MUST relay; an index entry whose Invite is never
            # sent would leave the owner's default selection naming nothing.
            raise BtNodePreconditionError(
                f"winning party '{winner_id}' is not an invitation recipient"
                f" on case '{case.id_}' (proposer '{self._proposer_id}')"
            )
