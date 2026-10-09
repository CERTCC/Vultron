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

"""A prototype-mode app holding one managed case, for live ledger stream tests.

Used two ways by ``test_ledger_stream_live.py``: built in-process and served
by uvicorn on a worker thread, and served by a uvicorn subprocess through
``--factory`` (:func:`make_seeded_app`) so the test can send it a real
SIGTERM.  Not a test module: pytest does not collect it.
"""

from fastapi import FastAPI

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.app import create_app
from vultron.adapters.driving.fastapi.deps import get_trigger_dl
from vultron.config import RunMode, get_config
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

ACTOR_ID = "urn:uuid:5f0c1e6a-3b52-4d1e-9a57-0d7c2a6e4b11"
CASE_ID = "urn:uuid:9b3f6d2e-7a41-4c08-8e15-2f6a9c0d3e77"

#: Entries :func:`make_seeded_app` stores before the server starts.
SEEDED_ENTRIES = 2


def build_app(dl: SqliteDataLayer) -> FastAPI:
    """Return a prototype app whose trigger routes read *dl*.

    Seeds the actor and a case it manages (so its store holds the canonical
    log and the demo ``sync-log-entry`` trigger can commit to it).
    """
    if get_config().mode != RunMode.PROTOTYPE:
        raise RuntimeError("the ledger stream is mounted only in prototype")
    dl.create(as_Service(id_=ACTOR_ID, name="Stream Actor Co"))
    case = as_VulnerabilityCase(
        id_=CASE_ID, name="Stream Case", attributed_to=ACTOR_ID
    )
    manager = as_CaseParticipant(
        attributed_to=ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case.actor_participant_index[ACTOR_ID] = manager.id_
    case.case_participants.append(manager.id_)
    dl.create(case)
    dl.create(manager)

    app = create_app(docs_url=None, openapi_url=None)
    app.dependency_overrides[get_trigger_dl] = lambda: dl
    return app


def make_seeded_app() -> FastAPI:
    """uvicorn ``--factory`` entry: :func:`build_app` with stored entries."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    app = build_app(dl)
    for i in range(SEEDED_ENTRIES):
        dl.save(
            CaseLedgerEntry(
                case_id=CASE_ID,
                log_index=i,
                log_object_id=f"{CASE_ID}/objects/{i}",
                event_type=f"seeded_{i}",
            )
        )
    return app
