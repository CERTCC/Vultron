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

"""A case's creation is one activity, delivered and ledgered (#5122, ADR-0157).

The ``Create(VulnerabilityCase)`` the CASE_MANAGER queues for the proposer is
the case's genesis entry, its sealed body verbatim (CLP-07-011, CLP-02-013).
The proposer seeds its replica from that same body, so the activity it holds
and the one every replica's ledger records are one.
"""

import json
from typing import Any, cast

import pytest

from test.support.ledger import ledger_entries
from test.support.ledger_rebuild import receive_into
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.use_case_result import HandlerDisposition

from .test_case_proposal import (
    _CASE_ACTOR_URI,
    _VENDOR_URI,
    _make_proposal,
    _run_create_proposal,
)


def _created(make_payload: Any) -> tuple[SqliteDataLayer, VulnerabilityCase]:
    """The CASE_MANAGER's store after it created a case from a proposal."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_CASE_ACTOR_URI)
    verdict = _run_create_proposal(dl, _make_proposal(), make_payload)
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    (case,) = [
        obj
        for obj in dl.list_objects("VulnerabilityCase")
        if isinstance(obj, VulnerabilityCase)
    ]
    return dl, case


def _sent_create(dl: SqliteDataLayer, case_id: str) -> dict[str, Any]:
    """The sealed body of the one ``Create(VulnerabilityCase)`` queued."""
    sent = [
        body
        for body in (
            read_sealed_body_dict(dl, item) for item in dl.outbox_list()
        )
        if body is not None
        and body.get("type") == "Create"
        and isinstance(body.get("object"), dict)
        and body["object"].get("id") == case_id
    ]
    assert len(sent) == 1, sent
    return sent[0]


@pytest.mark.spec("CLP-07-011")
@pytest.mark.spec("CLP-02-013")
def test_the_delivered_create_is_the_genesis_entry(make_payload):
    dl, case = _created(make_payload)

    genesis = ledger_entries(dl, case.id_)[0]

    assert genesis.semantic_type == "create_case"
    sent = _sent_create(dl, case.id_)
    assert sent == genesis.payload_snapshot
    # Key order too, at every depth: the snapshot is the body, not a re-render.
    assert json.dumps(sent) == json.dumps(genesis.payload_snapshot)
    # The CASE_MANAGER sends it once: one Create of the case is stored.
    assert len(dl.list_objects("Create")) == 1


@pytest.mark.spec("CLP-07-011")
@pytest.mark.spec("CBT-01-012")
def test_the_proposer_seeds_its_replica_from_the_genesis_entry(make_payload):
    """The proposer, given the genesis entry's body as its bootstrap, holds
    the case with its records and embargo as the CASE_MANAGER does."""
    manager, case = _created(make_payload)
    genesis = ledger_entries(manager, case.id_)[0]
    (report_id,) = map(str, case.vulnerability_reports)
    proposer = SqliteDataLayer("sqlite:///:memory:", actor_id=_VENDOR_URI)
    # The proposer holds the report it proposed the case for (CP-01-004).
    proposer.create(cast(VulnerabilityReport, manager.read(report_id)))
    proposer.create(
        VultronReportCaseLink(
            report_id=report_id, case_creator_id=_CASE_ACTOR_URI
        )
    )

    verdict = receive_into(proposer, genesis.payload_snapshot, _VENDOR_URI)

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    seeded = proposer.read(case.id_)
    assert isinstance(seeded, VulnerabilityCase)
    assert seeded.actor_participant_index == case.actor_participant_index
    for participant_id in case.actor_participant_index.values():
        copied = proposer.read(participant_id)
        assert isinstance(copied, CaseParticipant), participant_id
        assert copied == manager.read(participant_id), participant_id
    embargo_id = cast(str, case.active_embargo_id)
    assert proposer.read(embargo_id) == manager.read(embargo_id)
    assert isinstance(proposer.read(embargo_id), EmbargoEvent)
