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

"""Builders for the sync semantics."""

from typing import Any, cast

from test.support.ledger import ledger_entries
from test.support.objects import authored_at
from test.support.received import received_event
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.wire.as2.factories import (
    read_ledger_entry_activity,
    reject_log_entry_activity,
    rm_engage_case_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry,
)

from .._ledger_network import BYSTANDER, MANAGER, LedgerNetwork
from ..test_case_manager_note_replay import _set_rm
from . import Scenario, applied
from ._net import deliver

_BASE = "https://example.org/cases/rerun-sweep"


def _engaged(slug: str) -> LedgerNetwork:
    """A network whose CASE_MANAGER has committed and announced an engage."""
    net = LedgerNetwork(f"{_BASE}/{slug}", em_state=EM.NONE)
    _set_rm(net, BYSTANDER, RM.VALID)
    verdict = net.receive_event(
        MANAGER,
        deliver(
            net,
            rm_engage_case_activity(
                net.case(BYSTANDER),
                actor=BYSTANDER,
                to=[MANAGER],
                at=authored_at(),
            ),
        ).event,
    )
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    return net


def _wire(entry: CaseLedgerEntry) -> as_CaseLedgerEntry:
    return as_CaseLedgerEntry.model_validate(entry.model_dump(mode="json"))


def _entries(net: LedgerNetwork) -> list[CaseLedgerEntry]:
    entries = ledger_entries(net.stores[MANAGER], net.case_id)
    assert len(entries) >= 2, entries
    return entries


def at_replica(
    net: LedgerNetwork, body: dict[str, Any], replica: str, **kwargs: Any
) -> Scenario:
    """A scenario delivering the CASE_MANAGER's sealed *body* to *replica*.

    Signed by its author unless it is the body as sealed
    (:meth:`LedgerNetwork.delivered_body`), so an altered copy carries a
    valid proof.
    """
    stamped = net.delivered_body(body, receiver=replica)
    return Scenario(
        dl=net.stores[replica],
        event=received_event(
            parse_activity(stamped),
            as_sent=True,
            receiving_actor_id=replica,
        ),
        **kwargs,
    )


@applied(MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY)
def announce_case_ledger_entry() -> Scenario:
    """A replica applies the CASE_MANAGER's first entry, as announced."""
    net = _engaged("announce-ledger-entry")
    (body, *_) = net.ledger_announcements(BYSTANDER)
    return at_replica(net, cast(dict[str, Any], body), BYSTANDER)


@applied(MessageSemantics.REJECT_CASE_LEDGER_ENTRY)
def reject_case_ledger_entry() -> Scenario:
    """A replica that lost the announces rejects entry 1: replayed after 0."""
    net = _engaged("reject-ledger-entry")
    first, second, *_ = _entries(net)
    net.lose(MANAGER, to=BYSTANDER)
    return deliver(
        net,
        reject_log_entry_activity(
            _wire(second),
            ledger_position=LedgerPosition(
                log_index=first.log_index, entry_hash=first.entry_hash
            ),
            actor=BYSTANDER,
            to=[MANAGER],
            in_reply_to="https://example.org/activities/prompting-announce",
            at=authored_at(),
        ),
    )


@applied(MessageSemantics.READ_CASE_LEDGER_ENTRY)
def read_case_ledger_entry() -> Scenario:
    """A replica states it holds entry 0: the entries after are replayed."""
    net = _engaged("read-ledger-entry")
    first, *_ = _entries(net)
    net.lose(MANAGER, to=BYSTANDER)
    return deliver(
        net,
        read_ledger_entry_activity(
            _wire(first), actor=BYSTANDER, to=[MANAGER], at=authored_at()
        ),
    )
