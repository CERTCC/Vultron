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

import inspect
from typing import Any, cast

from test.support.embargo_register import (
    activate,
    propose,
    write_consent_rows,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.semantic_registry import extract_event, use_case_map
from vultron.wire.as2.parser import parse_activity

from .conftest import make_embargo_case_with_actor

MANAGER = "https://example.org/users/coord"
PROPOSER = "https://example.org/users/vendor"
#: The case owner: its answer decides a proposal (EP-09-005).
OWNER = "https://example.org/users/vendor-a"
#: A participant that is neither the proposer nor the owner.
BYSTANDER = "https://example.org/users/vendor-b"


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
        self.initial_embargo_id = embargo.id_
        self.stores: dict[str, SqliteDataLayer] = {MANAGER: manager_dl}
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
        event = extract_event(parse_activity(body)).model_copy(
            update={"receiving_actor_id": receiver}
        )
        return self.receive_event(receiver, event, without=without)

    def receive_event(
        self,
        receiver: str,
        event: Any,
        *,
        without: frozenset[str] = frozenset(),
    ):
        """Run the use case for an already-extracted *event* at *receiver*."""
        dl = self.stores[receiver]
        use_case = use_case_map()[event.semantic_type]
        offered: dict[str, Any] = {
            "sync_port": SyncActivityAdapter(dl),
            "trigger_activity": TriggerActivityAdapter(dl),
            "wire_render_port": As2WireRenderAdapter(),
        }
        accepted = inspect.signature(use_case).parameters
        ports = {
            k: v
            for k, v in offered.items()
            if k in accepted and k not in without
        }
        return use_case(dl, event, **ports).execute()

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

    def case(self, actor_id: str) -> VulnerabilityCase:
        return cast(
            VulnerabilityCase, self.stores[actor_id].read(self.case_id)
        )
