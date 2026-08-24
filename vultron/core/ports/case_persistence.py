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
from typing import Protocol

from vultron.core.models.protocols import PersistableModel
from vultron.core.models.protocol_pair import ProtocolPair
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

    @property
    def actor_id(self) -> str:
        """The canonical URI of the actor whose store this is (ADR-0071)."""
        ...

    def clone_for_actor(self, actor_id: str) -> "CasePersistence":
        """Return the store belonging to *actor_id*.

        The only way to reach a store other than this one, and deliberately
        explicit: ADR-0071 makes cross-actor access something a caller must
        name rather than something a forgotten filter grants by accident.
        """
        ...

    def create(self, record: "StorableRecord | PersistableModel") -> None: ...

    def read(
        self, object_id: str, raise_on_missing: bool = False
    ) -> PersistableModel | None: ...

    def save(self, obj: PersistableModel) -> None: ...

    def save_many(self, objs: list[PersistableModel]) -> None: ...

    def list_objects(self, type_key: str) -> Iterable[PersistableModel]: ...

    def find_case_by_report_id(
        self, report_id: str
    ) -> PersistableModel | None: ...

    def find_actor_by_short_id(
        self, short_id: str
    ) -> PersistableModel | None: ...

    def find_case_by_short_id(
        self, short_id: str
    ) -> PersistableModel | None: ...

    def find_protocol_pair(
        self,
        case_id: str,
        request_event_type: str,
        object_id: str,
        reply_event_types: frozenset[str],
    ) -> ProtocolPair: ...

    def delete(self, table: str, id_: str) -> bool: ...


class CaseOutboxPersistence(CasePersistence, Protocol):
    """CasePersistence extended for use cases that enqueue outbound activities.

    Only use cases and BT nodes that call ``outbox_append`` declare this type.
    If a ``ReceivedUseCase`` declares ``CaseOutboxPersistence``, that is a
    signal that it mixes received-message handling with outbound broadcast — an
    architectural smell worth investigating.

    The explicit-actor forms ``record_outbox_item(actor_id, activity_id)`` and
    ``outbox_list_for_actor(actor_id)`` are gone. They existed so that an
    *unscoped* DataLayer could name the actor whose queue to touch; every call
    site passed the executing actor's own id, so with a mandatory actor scope
    they are exactly ``outbox_append`` and ``outbox_list`` (ADR-0071).

    ``SqliteDataLayer`` satisfies this Protocol structurally — no declaration
    needed.
    """

    def outbox_append(self, activity_id: str) -> None: ...

    def outbox_list(self) -> list[str]: ...
