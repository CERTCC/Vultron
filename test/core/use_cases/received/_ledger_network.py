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
"""One store per actor, joined only by delivered sealed bodies (TB-06-007).

``LedgerNetwork`` seeds a CASE_MANAGER store holding an embargoed case and a
replica store for the owner and a bystander, then moves activities between
them only as the sealed body the sender's outbox would deliver, parsed and
routed the way the inbox routes it.  Shared by the ledger-replay integration
tests: a replica that never receives an activity directly still reaches the
CASE_MANAGER's state, from the ``Announce(CaseLedgerEntry)`` broadcast alone
(RSH-08-004, ADR-0108).
"""

import json
from typing import Any, cast

from test.support.embargo_register import (
    activate,
    propose,
    write_consent_rows,
)
from test.support.ledger import ledger_entries
from test.support.ledger_labels import label_mismatches
from test.support.ledger_rebuild import (
    assert_rebuilds_from_ledger,
    register_rows,
    replay_inbox,
    run_use_case,
)
from test.support.received import (
    in_step_sender_sequence,
    received_event,
    settle_as_the_inbox,
    stamped,
)
from test.support.signing import author_of, resigned
from vultron.adapters.driven.clock import SystemClock
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.ledger_position_stamp import (
    with_sender_ledger_position,
)
from vultron.adapters.driven.sender_sequence_stamp import with_sender_sequence
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driving.fastapi.sender_sequence_holds import (
    end_expired_holds,
)
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.behaviors.embargo.copy_commit import (
    PlannedEmbargoEntry,
    commit_and_apply_embargo_entries,
    consent_row_entry,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension, PxaDimension
from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    ConsentRowVerb,
)
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.sender_sequence import SenderSequenceCounter
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.services.sender_sequence_order import sender_sequence_order
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import add_status_to_participant_activity
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)

from .conftest import make_embargo_case_with_actor

MANAGER = "https://example.org/users/coord"
PROPOSER = "https://example.org/users/vendor"
#: The case owner: its Accept/Reject of the embargo decides a proposal
#: (EP-09-005, ADR-0122).
OWNER = "https://example.org/users/vendor-a"
#: A participant that is neither the proposer nor the owner.
BYSTANDER = "https://example.org/users/vendor-b"
#: The stores in a network that hold a replica: every one but the
#: CASE_MANAGER's.
REPLICAS = (OWNER, BYSTANDER)


#: Every network built in the current test, for the rebuild check
#: (``conftest._every_network_rebuilds_from_its_ledger``).
NETWORKS: list["LedgerNetwork"] = []


def _as_json(body: dict[str, Any]) -> str:
    """*body* as key-sorted JSON text, so two bodies compare as sent."""
    return json.dumps(body, sort_keys=True)


class LedgerNetwork:
    """One store per actor, and the outbox items each has delivered."""

    def __init__(
        self, case_id: str, *, owner: str = OWNER, em_state: EM = EM.ACTIVE
    ) -> None:
        self.case_id = case_id
        manager_dl, _, _case, embargo = make_embargo_case_with_actor(
            case_id,
            owner,
            extra_participants=[PROPOSER, BYSTANDER],
            case_manager_actor_id=MANAGER,
        )
        case_read = cast(VulnerabilityCase, manager_dl.read(case_id))
        # EM is derived from the register (ADR-0122): the embargo is open as
        # a proposal at PROPOSED and in force at ACTIVE.
        if em_state is EM.PROPOSED:
            propose(case_read, embargo.id_)
        elif em_state is EM.ACTIVE:
            activate(case_read, embargo.id_)
        assert case_read.em_state == em_state
        manager_dl.save(case_read)
        write_consent_rows(manager_dl, case_read)
        # Every participant has signed the active embargo, so each is active
        # while it is in force and a case-content send reaches it (CM-10-004).
        # With no embargo in force every send reaches every participant.
        signatories = (
            case_read.actor_participant_index.values()
            if em_state is EM.ACTIVE
            else []
        )
        for participant_id in signatories:
            participant = cast(
                CaseParticipant, manager_dl.read(participant_id)
            )
            manager_dl.save(
                participant.model_copy(
                    update={
                        "embargo_consents": [
                            EmbargoConsent(
                                embargo_id=embargo.id_,
                                state=EmbargoConsentState.AGREED,
                            )
                        ]
                    }
                )
            )
        # The owner holds CASE_OWNER on the roster, which the guard on its
        # decision for the case reads (HP-01-006, ADR-0122).
        owner_participant = cast(
            CaseParticipant,
            manager_dl.read(case_read.actor_participant_index[owner]),
        )
        owner_participant.add_role(CVDRole.CASE_OWNER)
        manager_dl.save(owner_participant)
        self.initial_embargo_id = embargo.id_
        self.stores: dict[str, SqliteDataLayer] = {MANAGER: manager_dl}
        #: The case file as it stood before the first ledger entry, the seed
        #: a rebuild from the ledger starts from (``rebuild_seed``).
        self._seed: list[CoreObject] | None = None
        #: Set by a test that writes the CASE_MANAGER's store outside the
        #: ledger on purpose (``bypass_ledger``); its rebuild is not checked.
        self.ledger_bypassed = False
        self._capture_seed_at_first_entry(manager_dl)
        NETWORKS.append(self)
        replicated = [
            case_id,
            embargo.id_,
            *(str(p) for p in case_read.actor_participant_index.values()),
        ]
        for actor_id in {owner, BYSTANDER} - {MANAGER}:
            replica = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
            for obj_id in replicated:
                obj = manager_dl.read(obj_id)
                if obj is not None:
                    replica.create(obj)
            self.stores[actor_id] = replica
        self._delivered: set[tuple[str, str]] = set()

    def _capture_seed_at_first_entry(
        self, manager_dl: SqliteDataLayer
    ) -> None:
        """Copy the case file just before the first entry is committed.

        The tests build the case outside the ledger and then adjust it (roles,
        RM, rows) before the scenario starts, so the seed is taken when the
        ledger starts, not when the network is built.
        """
        save = manager_dl.save

        def _save(obj: Any, *args: Any, **kwargs: Any) -> Any:
            if self._seed is None and isinstance(obj, CaseLedgerEntry):
                self._seed = self._case_file_records(manager_dl)
            return save(obj, *args, **kwargs)

        manager_dl.save = _save  # type: ignore[method-assign]

    def reopen(self, actor: str) -> SqliteDataLayer:
        """Replace *actor*'s DataLayer with a fresh instance on the same store.

        Stands in for a restart: only what the store persisted survives. The
        CASE_MANAGER's fresh instance keeps the seed capture, so the rebuild
        check still sees its first ledger entry.
        """
        reopened = self.stores[actor].clone_for_actor(actor)
        if actor == MANAGER:
            self._capture_seed_at_first_entry(reopened)
        self.stores[actor] = reopened
        return reopened

    def _case_file_records(self, dl: SqliteDataLayer) -> list[CoreObject]:
        case = cast(VulnerabilityCase, dl.read(self.case_id))
        ids = [
            self.case_id,
            *(str(p) for p in case.actor_participant_index.values()),
            *(str(_as_id(e.embargo)) for e in case.embargo_register),
        ]
        records = (dl.read(record_id) for record_id in ids)
        return [
            cast(CoreObject, r).model_copy(deep=True)
            for r in records
            if r is not None
        ]

    @property
    def rebuild_seed(self) -> list[CoreObject] | None:
        """The case file before the first entry, or ``None`` with no entries."""
        return self._seed

    def bypass_ledger(self) -> None:
        """Declare that this test writes the CASE_MANAGER's store directly.

        Such a test sets up a state no entry records, so a store rebuilt from
        the ledger cannot equal it; the rebuild check skips the network.
        """
        self.ledger_bypassed = True

    def receive(
        self,
        receiver: str,
        body: dict[str, Any],
        *,
        without: frozenset[str] = frozenset(),
        as_sent: bool = False,
    ):
        """Route *body* into *receiver*'s store as the inbox routes it.

        *without* names ports the receiver is composed without.  A body that
        states no ``ledgerPosition`` or ``senderSequence`` is first stamped
        as its sender's adapter would stamp it (:meth:`stamp`), so a test may
        hand over a factory's dump; *as_sent* delivers the body unstamped.
        Either way it is signed as :meth:`delivered_body` signs it, which
        replaces any proof the caller attached unless the body is the one
        its sender's outbox sealed.
        """
        body = (
            self._signed(body)
            if as_sent
            else self.delivered_body(body, receiver=receiver)
        )
        # A body :meth:`stamp` positioned is delivered as it stands, so a body
        # it left unnumbered stays unnumbered.
        event = received_event(
            parse_activity(body),
            as_sent=as_sent or "ledgerPosition" in body,
            receiving_actor_id=receiver,
        )
        return self.receive_event(receiver, event, without=without)

    def delivered_body(
        self, body: dict[str, Any], *, receiver: str | None = None
    ) -> dict[str, Any]:
        """*body* as its sender delivers it to *receiver*: stamped, signed.

        Stamped as :meth:`stamp` stamps it.  A body its sender's outbox
        sealed is then delivered as sealed, carrying the proof the outbox
        gave it (#5382); any other body is signed by its author, as its
        outbox would sign it (SIG-01-001), so a body a test built or altered
        carries a proof over what it sends.  A proof the caller attached is
        replaced, so a test of a bad proof cannot route it through here.
        """
        return self._signed(self.stamp(body, receiver=receiver))

    def _signed(self, body: dict[str, Any]) -> dict[str, Any]:
        """*body*, signed by its author unless its outbox sealed it so."""
        return body if self._sealed_as_sent(body) else resigned(body)

    def _sealed_as_sent(self, body: dict[str, Any]) -> bool:
        """Whether *body* is the body its sender's outbox sealed, unchanged.

        Compared as JSON text, not as Python values: ``True == 1`` in
        Python, so a body a test changed from ``1`` to ``true`` would
        otherwise pass for the sealed one and be delivered unsigned.
        """
        sender = self.stores.get(author_of(body))
        if sender is None or not isinstance(body.get("id"), str):
            return False
        sealed = read_sealed_body_dict(sender, body["id"])
        return sealed is not None and _as_json(sealed) == _as_json(body)

    def stamp(
        self, body: dict[str, Any], *, receiver: str | None = None
    ) -> dict[str, Any]:
        """*body* stating its sender's ledger tail and number, as sent.

        The tail comes from the sender's store when the network holds one
        (``with_sender_ledger_position``, SYNC-18-001), and is
        :data:`~test.support.received.TEST_SENDER_POSITION` for a sender the
        network keeps no store for.  A body that states a position, or whose
        object states its own, keeps it.

        Then the number (SYNC-21-001): a sender with a store numbers the body
        from its own counter, as its adapter numbers what it seals
        (``with_sender_sequence``), so bodies stamped in send order are
        numbered in send order, whatever order they are delivered in.  A
        sender the network keeps no store for is numbered in step with
        *receiver*, the CASE_MANAGER
        (:func:`~test.support.received.in_step_sender_sequence`).  A body
        that carries a number keeps it.

        A stamp changes the body, so a proof it carried no longer covers it:
        deliver a stamped body through :meth:`delivered_body`, which signs it
        again.
        """
        body = self._positioned(body)
        if "senderSequence" in body or "ledgerPosition" not in body:
            return body
        activity = parse_activity(body)
        sender_store = self.stores.get(str(_as_id(activity.actor)))
        number: int | None = None
        if sender_store is not None:
            with sender_store.transaction():
                number = with_sender_sequence(
                    sender_store, activity
                ).sender_sequence
        elif receiver is not None:
            number = in_step_sender_sequence(self.stores[receiver], activity)
        if number is None:
            return body
        return {**body, "senderSequence": number}

    def _positioned(self, body: dict[str, Any]) -> dict[str, Any]:
        """*body* stating its sender's ledger tail (:meth:`stamp`)."""
        if "ledgerPosition" in body:
            return body
        activity = parse_activity(body)
        sender_store = self.stores.get(str(_as_id(activity.actor)))
        stamped_activity = (
            with_sender_ledger_position(sender_store, activity)
            if sender_store is not None
            else stamped(activity)
        )
        position = stamped_activity.ledger_position
        if position is None:
            return body
        return {**body, "ledgerPosition": position.model_dump(by_alias=True)}

    def withdraw_unsent_numbers(self, actor: str) -> None:
        """Give back the numbers *actor* used on activities never delivered.

        A test that leaves a replica's own reply in its outbox and sends
        its own in its place stands for a sender that never sent that
        reply.  Its counter goes back to the last number the CASE_MANAGER
        has judged from it, so the test's own activity is numbered next, as
        it would have been (SYNC-21-002), rather than held behind a gap no
        delivery will fill.
        """
        expected = sender_sequence_order(
            self.stores[MANAGER], self.case_id, actor
        ).next_expected
        self.stores[actor].save(
            SenderSequenceCounter(
                case_id=self.case_id, sender_id=actor, last_used=expected - 1
            )
        )

    def end_expired_holds(self, actor: str = MANAGER) -> int:
        """Tick *actor*'s sender-sequence hold timer once, then replay.

        Ends each hold whose wait has passed by the clock (SYNC-21-011), as
        the app's hold timer does, and replays what that makes due, in
        number order.  Returns how many holds ended.
        """
        dl = self.stores[actor]
        ended = end_expired_holds(dl, clock=SystemClock())
        replay_inbox(dl, actor)
        return ended

    def receive_event(
        self,
        receiver: str,
        event: Any,
        *,
        without: frozenset[str] = frozenset(),
    ):
        """Run the use case for an already-extracted *event* at *receiver*.

        The record is then settled as the inbox's outcome stage settles it,
        so a second delivery of the same activity meets its seen-before door
        (ADR-0154).
        """
        result = run_use_case(self.stores[receiver], event, without=without)
        settle_as_the_inbox(self.stores[receiver], event, result)
        return result

    def queued(self, sender: str, *, to: str, type_: str | None = None):
        """*sender*'s outbox items addressed to *to*, oldest first."""
        dl = self.stores[sender]
        items = []
        for activity_id in dl.outbox_list():
            activity = cast(VultronActivity, dl.read(activity_id))
            recipients = [*(activity.to or []), *(activity.cc or [])]
            if to in recipients and (type_ is None or activity.type_ == type_):
                items.append(activity)
        return items

    def lose(self, sender: str, *, to: str, type_: str | None = None) -> None:
        """Drop every item *sender* queued for *to*: lost in transit.

        Every other pending item stays queued, in its order.
        """
        dl = self.stores[sender]
        lost = {a.id_ for a in self.queued(sender, to=to, type_=type_)}
        kept: list[str] = []
        while (activity_id := dl.outbox_pop()) is not None:
            if activity_id not in lost:
                kept.append(activity_id)
        for activity_id in kept:
            dl.outbox_append(activity_id)

    def deliver(self, sender: str, *, to: str, type_: str | None = None):
        """Deliver every not-yet-delivered item *sender* queued for *to*."""
        verdicts = []
        for activity in self.queued(sender, to=to, type_=type_):
            key = (to, activity.id_)
            if key in self._delivered:
                continue
            self._delivered.add(key)
            body = read_sealed_body_dict(self.stores[sender], activity.id_)
            assert body is not None, f"'{activity.id_}' was never sealed"
            verdicts.append((activity.type_, self.receive(to, body)))
        return verdicts

    def replay_ledger(self, replica: str) -> list[str]:
        """Hand *replica* the CASE_MANAGER's ledger broadcast, and only that.

        Each ``Announce(CaseLedgerEntry)`` the CASE_MANAGER queued for
        *replica* is delivered in chain order and must be applied.  Returns
        the semantic types delivered, in that order.
        """
        semantic_types = []
        for activity in self.queued(MANAGER, to=replica, type_="Announce"):
            body = read_sealed_body_dict(self.stores[MANAGER], activity.id_)
            entry = (body or {}).get("object") or {}
            if entry.get("type") != "CaseLedgerEntry":
                continue
            verdict = self.receive(replica, cast(dict[str, Any], body))
            assert verdict.disposition is HandlerDisposition.APPLIED, (
                entry.get("semanticType"),
                verdict.reason,
            )
            semantic_types.append(entry["semanticType"])
        return semantic_types

    def pxa_report(self, member: str, pxa: CS_pxa) -> Any:
        """*member*'s own ``Add(ParticipantStatus)`` reporting the case at *pxa*.

        A participant reports P, X or A only in the case status its
        participant status embeds (RSH-04-007); every other dimension
        restates the record the CASE_MANAGER holds, so only *pxa* is new.
        """
        case = self.case(MANAGER)
        participant = cast(
            CaseParticipant,
            self.stores[MANAGER].read(case.actor_participant_index[member]),
        )
        current = participant.participant_status
        assert current is not None
        status = ParticipantStatus(
            context=self.case_id,
            attributed_to=member,
            rm=current.rm,
            vf=current.vf,
            d=current.d,
            cvd_role=current.cvd_role,
            case_status=CaseStatus(
                context=self.case_id,
                attributed_to=member,
                em=EmDimension(state=case.em_state),
                pxa=PxaDimension(state=pxa),
            ),
        )
        return add_status_to_participant_activity(
            status,
            target=as_CaseParticipant(
                id_=participant.id_, context=self.case_id, attributed_to=member
            ),
            actor=member,
            to=[MANAGER],
        )

    def sealed_bodies(
        self, sender: str, *, to: str, type_: str, object_type: str
    ) -> list[dict[str, Any]]:
        """The sealed bodies of *sender*'s queued *type_* of *object_type*."""
        bodies = []
        for activity in self.queued(sender, to=to, type_=type_):
            body = read_sealed_body_dict(self.stores[sender], activity.id_)
            if ((body or {}).get("object") or {}).get("type") == object_type:
                bodies.append(cast(dict[str, Any], body))
        return bodies

    def ledger_announcements(self, replica: str) -> list[dict[str, Any]]:
        """The ``Announce(CaseLedgerEntry)`` bodies queued for *replica*."""
        return self.sealed_bodies(
            MANAGER,
            to=replica,
            type_="Announce",
            object_type="CaseLedgerEntry",
        )

    def processing_faults(self, sender: str) -> list[dict[str, Any]]:
        """The ``Create(ProcessingFault)`` bodies *sender* queued for the
        CASE_MANAGER."""
        return self.sealed_bodies(
            sender, to=MANAGER, type_="Create", object_type="ProcessingFault"
        )

    def record(self, holder: str, actor_id: str) -> CaseParticipant:
        """*holder*'s copy of *actor_id*'s participant record."""
        case = self.case(holder)
        return cast(
            CaseParticipant,
            self.stores[holder].read(case.actor_participant_index[actor_id]),
        )

    def drop_consent_row(self, holder: str, actor_id: str) -> None:
        """Make *holder*'s copy of *actor_id*'s record lose its consent row.

        A diverged replica: an ``Update`` of that row then has no row to
        start from, whatever state it carries.
        """
        record = self.record(holder, actor_id)
        record.embargo_consents = [
            row
            for row in record.embargo_consents
            if row.embargo_id != self.initial_embargo_id
        ]
        self.stores[holder].save(record)

    def consent_row_change(
        self, actor_id: str, state: EmbargoConsentState
    ) -> ConsentRowChange:
        """An update of *actor_id*'s row for the initial embargo to *state*."""
        return ConsentRowChange(
            verb=ConsentRowVerb.UPDATE,
            row=EmbargoConsent(
                embargo_id=self.initial_embargo_id,
                state=state,
                attributed_to=actor_id,
            ),
        )

    def planned_consent_entry(
        self, change: ConsentRowChange, cause_id: str
    ) -> PlannedEmbargoEntry:
        """The CASE_MANAGER's planned entry for *change*, caused by *cause_id*."""
        dl = self.stores[MANAGER]
        return consent_row_entry(
            datalayer=dl,
            trigger_activity=TriggerActivityAdapter(dl),
            actor_id=MANAGER,
            case_id=self.case_id,
            change=change,
            cause_id=cause_id,
            sync_port=SyncActivityAdapter(dl),
        )

    def diverged_announcement(
        self, replica: str, member: str, cause_id: str
    ) -> dict[str, Any]:
        """The CASE_MANAGER's announce of an entry *replica* diverged from.

        *replica*'s copy of *member*'s record loses its consent row, then the
        CASE_MANAGER commits *member*'s decline of the embargo: the entry
        extends *replica*'s chain but does not apply to its case.
        """
        self.drop_consent_row(replica, member)
        change = self.consent_row_change(member, EmbargoConsentState.DECLINED)
        commit_and_apply_embargo_entries(
            self.stores[MANAGER],
            self.case_id,
            [self.planned_consent_entry(change, cause_id)],
        )
        (body,) = self.sealed_bodies(
            MANAGER,
            to=replica,
            type_="Announce",
            object_type="CaseLedgerEntry",
        )
        return body

    def case(self, actor_id: str) -> VulnerabilityCase:
        return cast(
            VulnerabilityCase, self.stores[actor_id].read(self.case_id)
        )

    def register(self, actor_id: str) -> list[dict[str, Any]]:
        """*actor_id*'s embargo register, whole, as compared (CM-23-016)."""
        return register_rows(self.case(actor_id))


def rebuild_every_network(networks: list[LedgerNetwork]) -> None:
    """Rebuild each network's case from its CASE_MANAGER's ledger (#4294 AC-5).

    First, every entry the CASE_MANAGER holds must carry the registry's label
    for its payload (ADR-0140, #4724 AC-3).

    A network with no entries has nothing to rebuild, and one whose test
    wrote the CASE_MANAGER's store outside the ledger (``bypass_ledger()``)
    cannot be; every other must equal the CASE_MANAGER's, rebuilt as
    ``BYSTANDER`` from the case as it stood before the first entry.
    """
    for net in networks:
        held = ledger_entries(net.stores[MANAGER], net.case_id)
        # Every entry is the registry's label for its payload (ADR-0140,
        # #4724 AC-3), whether or not the network can be rebuilt.  The
        # CASE_MANAGER labelled each payload after rehydrating it against
        # its own store (SE-01-006), so the check does too.
        mismatches = label_mismatches(held, net.stores[MANAGER])
        assert not mismatches, "\n".join(mismatches)
        seed = net.rebuild_seed
        if net.ledger_bypassed:
            continue
        if seed is None:
            # No seed means no entry was committed; a ledger that holds one
            # anyway would skip the check silently.
            assert not held, (
                f"case '{net.case_id}' has ledger entries but no rebuild seed"
            )
            continue
        if not held:
            # The seed was taken when an entry was saved, but the act that
            # saved it failed and rolled back as one (ADR-0146).
            continue
        assert_rebuilds_from_ledger(
            net.stores[MANAGER], net.case_id, as_actor=BYSTANDER, seed=seed
        )
