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

"""The refusal notice carries the body; the stub replaces it after (CLP-10-073).

A precondition guard at the CASE_MANAGER that refuses an assertion owes the
sender one ``Reject`` of it, with the refused activity embedded as the sender
sent it (CLP-05-001).  The outcome stage then gives that body up for a receipt
stub (CLP-10-018).  Both must hold at once, which they do only because the
stage runs after the handling tree.

The CASE_MANAGER's store, case and ledger are built by the ledger network the
other received-side tests use, so the refusal driven here is a real one; the
delivery then goes through the production inbox wiring rather than the use
case alone, because the outcome stage belongs to the inbox.
"""

import pytest

from test.support.refusal_notice import assert_refusal_notice
from vultron.adapters.driving.fastapi.inbox_handler import make_dispatcher
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIDispatchAdapter,
    FastAPIIngressAdapter,
    FastAPIReceivedOutcomePort,
)
from vultron.core.behaviors.inbox import (
    InboxOutcomeStatus,
    process_payload,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.received_body import received_body_digest
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.services.received_activity import held_received_record
from vultron.wire.as2.parser import parse_activity

from ._ledger_network import BYSTANDER, MANAGER, LedgerNetwork
from .test_embargo_answer_idempotency import _answer_body, _invited
from .test_embargo_relay_replay import _owner_decides


@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("CLP-10-018")
@pytest.mark.spec("CLP-10-073")
def test_the_notice_embeds_the_body_and_the_stub_replaces_it():
    """One delivery: the ``Reject`` carries the body, the record keeps none."""
    net = LedgerNetwork("https://example.org/cases/notice-then-stub")
    embargo_id, invite_id = _invited(net, BYSTANDER, "notice-then-stub")
    decided = _owner_decides(net, embargo_id, accept=False)
    assert decided.disposition is HandlerDisposition.APPLIED, decided.reason
    body = net.stamp(
        _answer_body(net, BYSTANDER, invite_id, accept=False, tag="late")
    )
    store = net.stores[MANAGER]

    outcome = process_payload(
        body,
        FastAPIIngressAdapter(dl=store),
        FastAPIDispatchAdapter(
            dl=store, actor_id=MANAGER, dispatcher=make_dispatcher()
        ),
        received_outcome_port=FastAPIReceivedOutcomePort(store),
    )

    assert outcome.status is InboxOutcomeStatus.REJECTED
    # The notice went out with the refused activity embedded as received: the
    # body was still there while the tree ran (CLP-05-001, DL-06-004).
    assert_refusal_notice(
        store,
        manager=MANAGER,
        refused_id=body["id"],
        asserter=BYSTANDER,
        reason="neither the active embargo nor an open proposal",
        case_id=net.case_id,
    )
    # And what remains of the refused message is the receipt, not the message.
    record = held_received_record(store, body["id"])
    assert isinstance(record, ReceivedActivityRecord)
    assert record.is_receipt_stub
    assert record.received_body is None
    assert record.sender_id == BYSTANDER
    assert record.refusal_reason is not None
    assert "neither the active embargo nor an open proposal" in (
        record.refusal_reason
    )
    sealed = parse_activity(body).received_evidence_json
    assert sealed is not None
    assert record.body_hash == received_body_digest(sealed)
