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
"""A demo client that reads a real store, and a case replica to put in it.

For tests of demo helpers that read an actor's replica through its DataLayer
inspection routes: :class:`StoreClient` answers ``get(dl_path(key))`` from a
real :class:`SqliteDataLayer` exactly as the route does
(``AS2JSONResponse`` of what ``dl.read`` returns), so the helper validates
the same bytes it would read from a container.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import unquote

import httpx2 as httpx

from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.responses import AS2JSONResponse
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.report import VulnerabilityReport
from vultron.enums import CVDRole


class StoreClient:
    """Stand-in ``DataLayerClient`` whose reads are served from *store*.

    Attributes:
        actor_id: The actor whose store this client inspects.
        paths: Every path :meth:`get` was asked for, in order.
    """

    def __init__(self, store: SqliteDataLayer) -> None:
        self._store = store
        self.actor_id = store.actor_id
        self.paths: list[str] = []

    def dl_path(self, key: str = "") -> str:
        """The key itself: the store is this client's only one."""
        return key

    def get(self, path: str) -> dict[str, Any]:
        """The stored object *path* names, as the inspection route serves it.

        Raises:
            httpx.HTTPStatusError: The store holds no such object (404).
        """
        self.paths.append(path)
        obj = self._store.read(unquote(path))
        if obj is None:
            request = httpx.Request("GET", f"http://test/{path}")
            raise httpx.HTTPStatusError(
                "404 Not Found",
                request=request,
                response=httpx.Response(404, request=request),
            )
        body: dict[str, Any] = json.loads(bytes(AS2JSONResponse(obj).body))
        return body


def seed_case_replica(
    store: SqliteDataLayer,
    case_id: str,
    participants: Mapping[str, Sequence[CVDRole]],
    report_id: str = "urn:test:report",
) -> VulnerabilityCase:
    """Store a case holding one report and *participants*, by reference.

    Args:
        store: Where the replica goes.
        case_id: The case's id.
        participants: Each participant's actor id and its roles.
        report_id: The one report's id.

    Returns:
        The case as the store holds it.
    """
    owner = next(iter(participants))
    report = make(
        VulnerabilityReport,
        id_=report_id,
        attributed_to=owner,
        content="libexample 2.1 is bundled by the second vendor.",
    )
    store.create(report)
    case = make(VulnerabilityCase, id_=case_id, attributed_to=owner)
    case.add_report(report.id_)
    for actor_id, roles in participants.items():
        participant = make(
            CaseParticipant,
            attributed_to=actor_id,
            context=case_id,
            case_roles=list(roles),
        )
        case.add_participant(participant)
        store.create(participant)
    store.save(case)
    stored = store.read_case(case_id)
    assert stored is not None
    return stored


__all__ = ["StoreClient", "seed_case_replica"]
