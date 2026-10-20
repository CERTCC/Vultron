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

from typing import Any, cast

from test.support.embargo_register import (
    activate,
    propose,
    write_consent_rows,
)
from test.support.ledger import ledger_entries
from test.support.ledger_rebuild import (
    assert_rebuilds_from_ledger,
    received_event,
    register_rows,
    run_use_case,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models._helpers import _as_id
from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension, PxaDimension
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.use_case_result import HandlerDisposition
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
    ):
        """Route *body* into *receiver*'s store as the inbox routes it.

        *without* names ports the receiver is composed without.
        """
        event = received_event(parse_activity(body), receiver)
        return self.receive_event(receiver, event, without=without)

    def receive_event(
        self,
        receiver: str,
        event: Any,
        *,
        without: frozenset[str] = frozenset(),
    ):
        """Run the use case for an already-extracted *event* at *receiver*."""
        return run_use_case(self.stores[receiver], event, without=without)

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
        participant status embeds (RSH-04-001); every other dimension
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

    def case(self, actor_id: str) -> VulnerabilityCase:
        return cast(
            VulnerabilityCase, self.stores[actor_id].read(self.case_id)
        )

    def register(self, actor_id: str) -> list[dict[str, Any]]:
        """*actor_id*'s embargo register, whole, as compared (CM-23-016)."""
        return register_rows(self.case(actor_id))


def rebuild_every_network(networks: list[LedgerNetwork]) -> None:
    """Rebuild each network's case from its CASE_MANAGER's ledger (#4294 AC-5).

    A network with no entries has nothing to rebuild, and one whose test
    wrote the CASE_MANAGER's store outside the ledger (``bypass_ledger()``)
    cannot be; every other must equal the CASE_MANAGER's, rebuilt as
    ``BYSTANDER`` from the case as it stood before the first entry.
    """
    for net in networks:
        seed = net.rebuild_seed
        if net.ledger_bypassed:
            continue
        if seed is None:
            # No seed means no entry was committed; a ledger that holds one
            # anyway would skip the check silently.
            assert not ledger_entries(net.stores[MANAGER], net.case_id), (
                f"case '{net.case_id}' has ledger entries but no rebuild seed"
            )
            continue
        assert_rebuilds_from_ledger(
            net.stores[MANAGER], net.case_id, as_actor=BYSTANDER, seed=seed
        )
