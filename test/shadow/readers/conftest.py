"""Fixtures for the live Vultron case reader's tests: a node holding a case."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from test.support.case_owner import CASE_OWNER_ID
from test.support.ledger_stream import recording_rows
from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

#: The recorded case a demo node holds.
RECORDING = RECORDINGS_DIR / "rv" / "case-actor.jsonl"


@pytest.fixture
def node_dl() -> Iterator[SqliteDataLayer]:
    actor = make(as_Service, name="Case Actor")
    reset_datalayer(actor.id_)
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
    store.clear_all()
    store.create(actor)
    yield store
    store.close()
    reset_datalayer(actor.id_)


@pytest.fixture
def demo_case(node_dl: SqliteDataLayer) -> str:
    """The rv recording's case and ledger, held by the node."""
    rows = recording_rows(RECORDING)
    case_id = str(rows[0]["caseId"])
    node_dl.create(
        make(
            as_VulnerabilityCase,
            id_=case_id,
            attributed_to=CASE_OWNER_ID,
            name="RV-DEMO",
        )
    )
    for row in reversed(rows):  # stored out of order, served in order
        node_dl.save(CaseLedgerEntry.model_validate(row))
    return case_id
