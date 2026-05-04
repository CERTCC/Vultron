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

"""Narrow outbound ports for core domain use cases and BT nodes.

:class:`CasePersistence` covers the methods called by
``vultron/core/`` use cases — excluding inbox/outbox queues, health,
diagnostics, and low-level storage primitives (``update``, ``delete``,
``clear_*``, ``count_all``) that belong to the adapter layer.

:class:`CaseOutboxPersistence` extends :class:`CasePersistence` for the
small number of use cases and BT nodes that also enqueue outbound activities.
Declaring ``CaseOutboxPersistence`` on a ``Received`` use case is an
architectural smell — it signals that the handler mixes inbound processing
with outbound broadcast.

``SqliteDataLayer`` satisfies both Protocols structurally with no declaration
needed (Python structural subtyping).

See also:
    - ``specs/datalayer.yaml`` DL-03-001, DL-03-002
    - GitHub issue #403
"""

from collections.abc import Iterable
from typing import Any, Protocol

from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import StorableRecord


class CasePersistence(Protocol):
    """Narrow outbound port for core domain use cases and BT nodes.

    Covers the methods called by ``vultron/core/`` use cases. Excludes
    low-level storage primitives (``update``, ``delete``), infrastructure
    operations (inbox/outbox queues, ``ping``, ``clear_*``), and diagnostics
    (``get_all``, ``count_all``).

    ``SqliteDataLayer`` satisfies this Protocol structurally — no declaration
    needed.
    """

    def create(self, record: "StorableRecord | PersistableModel") -> None: ...

    def read(
        self, object_id: str, raise_on_missing: bool = False
    ) -> PersistableModel | None: ...

    def get(
        self, table: str | None, id_: str | None
    ) -> "PersistableModel | dict[str, Any] | None": ...

    def save(self, obj: PersistableModel) -> None: ...

    def by_type(self, type_: str) -> "dict[str, dict[str, Any]]": ...

    def list_objects(self, type_key: str) -> Iterable[PersistableModel]: ...

    def find_case_by_report_id(
        self, report_id: str
    ) -> PersistableModel | None: ...

    def find_actor_by_short_id(
        self, short_id: str
    ) -> PersistableModel | None: ...


class CaseOutboxPersistence(CasePersistence, Protocol):
    """CasePersistence extended for use cases that enqueue outbound activities.

    Only use cases and BT nodes that call ``record_outbox_item`` or
    ``outbox_append`` declare this type. If a ``ReceivedUseCase`` declares
    ``CaseOutboxPersistence``, that is a signal that it mixes received-message
    handling with outbound broadcast — an architectural smell worth
    investigating.

    ``SqliteDataLayer`` satisfies this Protocol structurally — no declaration
    needed.
    """

    def record_outbox_item(self, actor_id: str, activity_id: str) -> None: ...

    def outbox_append(self, activity_id: str) -> None: ...
