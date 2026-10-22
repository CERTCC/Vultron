"""Ledger effect nodes for the embargo revision relay (EP-09-007, ADR-0113).

The CASE_MANAGER commits three kinds of entry while it relays an embargo
negotiation: the proposal it received, each ``Invite(EmbargoEvent)`` it relays
to a participant, and each participant's ``Accept`` or ``Reject`` of its
Invite — the case owner's included, which is the owner's consent (ADR-0122).
A re-invite of a late accepter whose embargo went stale (EMB-17-003) is a
relayed Invite like any other (ADR-0152); the owner's decision on a proposal
has a semantic type of its own (``activation_effect.py``).  A participant
replica writes none of that state when the activity reaches it directly
(EP-09-003, RSH-08-003); it copies the state from the
``Announce(CaseLedgerEntry)`` broadcast through these nodes (RSH-08-004,
ADR-0108).

Each node copies; none runs ``EmbargoLifecycle`` (ADR-0124, CM-23-016).  A
proposal entry is its whole register step, so its slot copies the
``PROPOSE`` step through the one apply function
(``ApplyEmbargoChangeFromLedgerNode``); an ``Accept`` or ``Reject`` entry is
its sender's row's entry, so its slot copies the row the answer states
(ADR-0122).  Every other consent row an act changes (a proposal's new rows,
a relayed Invite's ``INVITED`` row) follows as the
CASE_MANAGER's own ``Create`` or ``Update(EmbargoConsent)`` entry
(CLP-07-013), which the consent slot copies
(``ApplyEmbargoConsentFromLedgerNode``), so the Invite slots write no
row.  Every slot stores the embargo the entry carries, and the
relay slot indexes the proposal on the proposer's replica.

Regime 2 (ADR-0087): a replica that holds no copy of the case skips the entry
with SUCCESS.  A replica that holds the case but cannot reconstruct the
embargo the entry names fails, which blocks persisting the entry
(SYNC-12-001) — persisting it would record a transition the replica never
applied.
"""

from __future__ import annotations

from typing import Any

from py_trees.common import Status

from vultron.core.behaviors.embargo.proposal_index import (
    record_embargo_proposal_index,
)
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.sync.nodes._helpers import (
    _extract_id_from_field,
    _LedgerEffectNode,
)
from vultron.core.behaviors.sync.nodes.embargo_copy_effect import (
    ApplyEmbargoChangeFromLedgerNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    EmbargoChange,
    RegisterStep,
    RegisterStepKind,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.wire_keys import wire_key
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import snapshot_actor_id
from vultron.core.services.carried_embargo import (
    carried_entry_embargo,
    entry_embargo,
)
from vultron.errors import VultronError, VultronNotFoundError


def _answered_invite(snapshot: dict[str, Any]) -> Any:
    """Return the Invite an ``Accept``/``Reject`` snapshot answers."""
    return snapshot.get("object")


def _embargo_of_invite(invite: Any) -> Any:
    """Return the ``EmbargoEvent`` (inline dict or bare id) an Invite carries."""
    if isinstance(invite, dict):
        return invite.get("object")
    return None


class _EmbargoRelayEffectNode(_LedgerEffectNode):
    """Shared frame: resolve the replica case and the embargo the entry names."""

    def _resolve(
        self, embargo_data: Any
    ) -> tuple[VulnerabilityCase, str] | Status:
        """Return ``(case, embargo_id)``, or the ``Status`` to return early.

        SUCCESS when this replica holds no copy of the case (Regime 2).
        FAILURE when the entry names no embargo, or names one this replica can
        neither find nor reconstruct (EMB-18-003).
        """
        if (f := self._require_datalayer()) is not None:
            return f
        entry = self._get_entry()
        case = self._resolve_case_replica(entry.case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica

        embargo_id = _extract_id_from_field(embargo_data)
        if not embargo_id:
            self.feedback_message = (
                f"'{entry.semantic_type}' entry on case '{entry.case_id}' names"
                " no embargo"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if not self._store_embargo(embargo_data, embargo_id):
            return Status.FAILURE
        return case, embargo_id

    def _store_embargo(self, embargo_data: Any, embargo_id: str) -> bool:
        """Persist the entry's inline ``EmbargoEvent`` unless already stored.

        The canonical entry carries the object inline, so the replica stores
        it from there rather than fetching it from the proposer (EMB-18-003,
        CLP-10-017).  A bare id is enough when the record is already here; an
        inline copy, or a held record, whose ``context`` is neither the case
        nor one of its reports is refused, as the case-seeding path refuses
        one (``carried_entry_embargo``, EMB-18-004).
        """
        assert self.datalayer is not None
        try:
            embargo = carried_entry_embargo(
                self.datalayer, self._get_entry().case_id, embargo_data
            )
        except VultronError as exc:
            self.feedback_message = str(exc)
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return False
        if embargo is None:
            return True
        self.datalayer.create(embargo)
        self.logger.debug(
            "%s: stored embargo '%s' from the canonical entry",
            self.name,
            embargo_id,
        )
        return True

    def _index_for_proposer(
        self,
        case: VulnerabilityCase,
        embargo_id: str,
        snapshot: dict[str, Any],
    ) -> None:
        """Index the Invite on the proposer's replica only (EP-08-002).

        Only while the embargo is an open proposal: a re-invite to the
        embargo in force names its proposer too (ADR-0152), and the
        activation already took that embargo out of the index (EP-08-003).
        """
        assert self.datalayer is not None
        if not case.proposal_is_undecided(embargo_id):
            return
        # Normalised: the snapshot keeps the relay's spelling (OID-01-006).
        proposer_id = snapshot_actor_id(
            snapshot.get(wire_key("attributed_to"))
        )
        invite_id = _extract_id_from_field(snapshot.get("id"))
        if not proposer_id or proposer_id != self.actor_id or not invite_id:
            return
        record_embargo_proposal_index(
            self.datalayer, case.id_, embargo_id, invite_id, overwrite=False
        )

    def _delegate(self, node: DataLayerActionWithPorts) -> Status:
        """Run a received-side record node in this node's store and actor.

        For the slots not yet copying (#4716).
        """
        node.datalayer = self.datalayer
        node.actor_id = self.actor_id
        status = node.update()
        self.feedback_message = node.feedback_message
        return status

    def _store_only(self, embargo_data: Any) -> Status:
        """Store the embargo the entry names; write nothing else.

        For an entry whose consent consequences follow as entries of their
        own (ADR-0124, CLP-07-013): each row the act changed (none, one, or
        several, as for a withdrawal) is a later CASE_MANAGER
        ``Update(EmbargoConsent)`` entry, which the consent slot copies.
        """
        resolved = self._resolve(embargo_data)
        if isinstance(resolved, Status):
            return resolved
        case, embargo_id = resolved
        entry = self._get_entry()
        self.feedback_message = (
            f"'{entry.semantic_type}' entry '{entry.id_}' of embargo"
            f" '{embargo_id}' on case '{case.id_}': each consent row it"
            " changes follows as its own entry"
        )
        self.logger.debug("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


def _carried_embargo(
    datalayer: CasePersistence, case_id: str, embargo_data: Any
) -> EmbargoEvent:
    """The ``EmbargoEvent`` an entry carries, inline or by id.

    The entry carries it inline (EMB-18-003, CLP-10-017); a bare id is
    enough when this store already holds the record.  An inline copy, or a
    held record, whose ``context`` is neither the case nor one of its
    reports is refused, as the case-seeding path refuses one
    (:func:`~vultron.core.services.carried_embargo.entry_embargo`,
    EMB-18-004).

    Raises:
        TypeError: the entry names an embargo by id only, and this store does
            not hold it.
        ValueError: the entry names no embargo, the inline embargo is
            malformed, or it or the held record belongs to another case.
    """
    try:
        return entry_embargo(datalayer, case_id, embargo_data)
    except VultronNotFoundError as exc:
        raise TypeError(
            "the entry names an embargo by id only, and this store does not"
            f" hold it: {exc}"
        ) from exc


def _store_carried_embargo(
    datalayer: CasePersistence, embargo: EmbargoEvent
) -> None:
    """Store *embargo* unless this store already holds it."""
    if datalayer.read(embargo.id_) is None:
        datalayer.create(embargo)


class _CopiedEmbargoEntryNode(ApplyEmbargoChangeFromLedgerNode):
    """Shared frame: a copy slot whose entry carries an ``EmbargoEvent``.

    A subclass names where the embargo sits in the snapshot
    (:meth:`_embargo_data`) and the change the entry carries
    (:meth:`_change_for`); the frame copies the change through the one apply
    function, then stores the embargo and runs :meth:`_after_apply`.
    """

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name)
        self._embargo: EmbargoEvent | None = None

    def _embargo_data(self, snapshot: dict[str, Any]) -> Any:
        raise NotImplementedError

    def _change_for(
        self, entry: CaseLedgerEntry, embargo: EmbargoEvent
    ) -> EmbargoChange:
        raise NotImplementedError

    def _after_apply(
        self, case: VulnerabilityCase, entry: CaseLedgerEntry
    ) -> None:
        """Bookkeeping once the change is in place; the default does none."""

    def _change(self, entry: CaseLedgerEntry) -> EmbargoChange:
        assert self.datalayer is not None
        self._embargo = _carried_embargo(
            self.datalayer,
            entry.case_id,
            self._embargo_data(entry.payload_snapshot),
        )
        return self._change_for(entry, self._embargo)

    def update(self) -> Status:
        self._embargo = None
        status = super().update()
        if status is not Status.SUCCESS or self._embargo is None:
            return status  # refused, or Regime 2 (ADR-0087)
        assert self.datalayer is not None
        entry = self._get_entry()
        _store_carried_embargo(self.datalayer, self._embargo)
        case = self._resolve_case_replica(entry.case_id)
        if case is not None:
            self._after_apply(case, entry)
        return status


class ApplyEmbargoProposalFromLedgerNode(_CopiedEmbargoEntryNode):
    """Copy the ``PROPOSE`` step a proposal entry carries (EP-09-001, ADR-0124).

    The proposal's ``Invite(EmbargoEvent)`` is its whole register step
    (ADR-0122): the replica copies the ``PROPOSED`` entry, embargo inline,
    through the one apply function, so EM derives ``PROPOSED`` (no embargo
    in force) or ``REVISE`` (a revision).  It writes no consent row: the rows
    the proposal created (the proposer's ``AGREED``, every other
    participant's ``UNINVITED``) follow as the CASE_MANAGER's own
    ``Create(EmbargoConsent)`` entries, which the consent slot copies.  It
    stores the proposed ``EmbargoEvent`` from the entry, and records the
    proposal in ``pending_embargo_proposal_index`` only when this replica
    has no entry for the embargo yet, so the Invite actually addressed to
    this replica keeps its place there.

    When the CASE_MANAGER proposed the terms itself, each Invite it relays is
    self-attributed (``attributedTo`` is the manager, the proposer), so the
    classifier reads it as this proposal slot rather than the relay slot
    (``is_relayed_embargo_invite``).  Its ``PROPOSE`` is already in place,
    since the manager's proposal entry came first, so it is a no-op here;
    the invitee's row follows as its own entry (EP-09-002, #4085).

    An entry whose step does not apply to this replica's case is held for gap
    handling, never patched over (``ApplyEmbargoChangeFromLedgerNode``).
    """

    def _embargo_data(self, snapshot: dict[str, Any]) -> Any:
        return snapshot.get("object")

    def _change_for(
        self, entry: CaseLedgerEntry, embargo: EmbargoEvent
    ) -> EmbargoChange:
        return RegisterStep(kind=RegisterStepKind.PROPOSE, embargo=embargo)

    def _after_apply(
        self, case: VulnerabilityCase, entry: CaseLedgerEntry
    ) -> None:
        assert self.datalayer is not None and self._embargo is not None
        proposal_id = _extract_id_from_field(entry.payload_snapshot.get("id"))
        if proposal_id:
            record_embargo_proposal_index(
                self.datalayer,
                case.id_,
                self._embargo.id_,
                proposal_id,
                overwrite=False,
            )


class _ApplyEmbargoAnswerFromLedgerNode(_CopiedEmbargoEntryNode):
    """Copy the row an answer's entry states (ADR-0122, CLP-07-013).

    ``Accept`` or ``Reject(Invite(EmbargoEvent))`` is its sender's own
    consent, the case owner's included, and its entry is that row's entry:
    the replica copies the ``AGREED`` or ``DECLINED`` row the answer states
    (:meth:`ConsentRowChange.answer`) through the one apply function.  It
    moves no register entry.  The CASE_MANAGER commits only an answer whose
    row it could write, so one that does not apply here is held for gap
    handling, never patched over.
    """

    #: ``True`` for ``Accept``, ``False`` for ``Reject``.
    _ACCEPT: bool

    def _embargo_data(self, snapshot: dict[str, Any]) -> Any:
        return _embargo_of_invite(_answered_invite(snapshot))

    def _change_for(
        self, entry: CaseLedgerEntry, embargo: EmbargoEvent
    ) -> EmbargoChange:
        # The answerer's row is keyed by its canonical id; the snapshot keeps
        # the sender's spelling (OID-01-006).
        actor_id = snapshot_actor_id(entry.payload_snapshot.get("actor"))
        if not actor_id:
            raise TypeError("the answer names no actor")
        return ConsentRowChange.answer(
            embargo_id=embargo.id_, actor_id=actor_id, accept=self._ACCEPT
        )


class ApplyEmbargoAcceptanceFromLedgerNode(_ApplyEmbargoAnswerFromLedgerNode):
    """Copy the ``AGREED`` row an ``Accept`` of an embargo Invite states (MSM-07-003)."""

    _ACCEPT = True


class ApplyEmbargoRejectionFromLedgerNode(_ApplyEmbargoAnswerFromLedgerNode):
    """Copy the ``DECLINED`` row a ``Reject`` of an embargo Invite states (MSM-07-004)."""

    _ACCEPT = False


class ApplyEmbargoInviteFromLedgerNode(_EmbargoRelayEffectNode):
    """Store an Invite the CASE_MANAGER relayed (EP-09-002, EP-09-004).

    The invitee's PEC ``INVITE`` and the Invite's RSVP deadline are the
    CASE_MANAGER's next entry, an ``Update(EmbargoConsent)`` carrying the
    row, which the consent slot copies (ADR-0124, CM-28-013); this slot
    writes no row.  It stores the embargo the entry carries.

    On the proposer's own replica — the Invite's ``attributedTo`` — the Invite
    is also recorded in ``pending_embargo_proposal_index`` when the replica has
    no entry for the embargo yet, so the proposer's default selection reaches
    the revision (EP-08-002).  A proposer that is not the CASE_MANAGER indexes
    nothing when it asks (EP-09-008), and the creation-time revision has no
    proposal activity (EP-04-011), so for both the relayed Invite is the only
    entry the proposer's replica learns the proposal from; when the replica
    already holds an entry for the embargo this is a no-op.  An invitee indexes the Invite when it
    answers, so this node writes no index for anyone else: an entry here would
    make the invitee's idempotency guard read the Invite as already answered.
    """

    def update(self) -> Status:
        entry = self._get_entry()
        snapshot = entry.payload_snapshot
        resolved = self._resolve(snapshot.get("object"))
        if isinstance(resolved, Status):
            return resolved
        case, embargo_id = resolved
        recipients = snapshot.get("to") or []
        if not isinstance(recipients, list) or len(recipients) != 1:
            self.feedback_message = (
                f"relayed Invite on case '{case.id_}' names"
                f" {len(recipients) if isinstance(recipients, list) else 0}"
                " recipients; a relayed Invite has exactly one (EP-09-010)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if case.embargo_register_entry(embargo_id) is None:
            # The proposal is committed before its relay (EP-09-002), so a
            # replica replaying the relay holds the entry; one that does not
            # has a gap, and the entry is not marked applied (SYNC-12-001).
            self.feedback_message = (
                f"relayed Invite of embargo '{embargo_id}' on case"
                f" '{case.id_}' names an embargo this replica's register does"
                " not hold"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        self._index_for_proposer(case, embargo_id, snapshot)
        self.feedback_message = (
            f"Stored relayed Invite of embargo '{embargo_id}' on case"
            f" '{case.id_}'; the invitee's row follows as its own entry"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


class ApplyCreatedEmbargoFromLedgerNode(_EmbargoRelayEffectNode):
    """Store the embargo a ``create_embargo_event`` entry carries (CLP-07-013).

    The CASE_MANAGER commits one right after a case's genesis entry for each
    embargo the creation wrote, such as the default embargo.  The case
    already names it in its register, so this slot moves nothing: it stores
    the record, its start and end times included, which the replica's own
    embargo decisions read (#5122).  A record already held passes as a
    no-op; one for another case is refused (EMB-18-004).
    """

    def update(self) -> Status:
        resolved = self._resolve(
            self._get_entry().payload_snapshot.get("object")
        )
        if isinstance(resolved, Status):
            return resolved
        case, embargo_id = resolved
        self.feedback_message = (
            f"Stored embargo '{embargo_id}' of case '{case.id_}' from its"
            " create_embargo_event entry"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


__all__ = [
    "ApplyCreatedEmbargoFromLedgerNode",
    "ApplyEmbargoProposalFromLedgerNode",
    "ApplyEmbargoInviteFromLedgerNode",
    "ApplyEmbargoAcceptanceFromLedgerNode",
    "ApplyEmbargoRejectionFromLedgerNode",
]
