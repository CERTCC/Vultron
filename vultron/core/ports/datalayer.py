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

"""Outbound (driven) port — storage interface used by the core domain layer.

Concrete implementations (e.g. ``TinyDbDataLayer``) live in the adapter
layer at ``vultron/adapters/driven/`` and import this Protocol to
verify structural conformance.

Port direction: **outbound (driven)** — core calls ``read()``,
``create()``, ``update()``, ``delete()``, and ``list()`` to persist and
retrieve domain objects through whatever storage backend the adapter
provides.

No adapter-layer types (``Record``, ``TinyDB``, etc.) appear here.

See also: ``notes/architecture-ports-and-adapters.md`` "Core Port Taxonomy".
"""

from typing import Any, Protocol

from pydantic import BaseModel

from vultron.core.models.protocols import PersistableModel


class StorableRecord(BaseModel):
    """Minimal typed record passed to ``DataLayer.create()`` and ``update()``.

    Core BT nodes construct ``StorableRecord`` objects without importing the
    adapter-layer ``Record`` class.  Adapter implementations receive a
    ``StorableRecord`` (or a subclass such as ``Record``) and may add extra
    behaviour (e.g. ``from_obj`` / ``to_obj``) without coupling the port to
    wire-layer types.
    """

    id_: str
    type_: str
    data_: dict


class DataLayer(Protocol):
    """Protocol for a data layer.

    Defines the minimum interface that any concrete storage adapter must
    satisfy.  ``update`` accepts ``StorableRecord`` — a Pydantic model
    defined in this module — so that the core layer passes validated, typed
    objects to the port rather than raw dicts or ``Any``.  ``create``
    additionally accepts a plain ``BaseModel`` for callers that have not yet
    been updated to produce ``StorableRecord`` objects (V-15 through V-19,
    tracked in P65-5/P65-6).
    """

    def create(self, record: "StorableRecord | PersistableModel") -> None: ...

    def read(
        self, object_id: str, raise_on_missing: bool = False
    ) -> PersistableModel | None: ...

    def get(
        self, table: str | None, id_: str | None
    ) -> PersistableModel | dict[str, Any] | None: ...

    def update(self, id_: str, record: StorableRecord) -> bool: ...

    def delete(self, table: str, id_: str) -> bool: ...

    def clear_table(self, table: str) -> None: ...

    def clear_all(self) -> None: ...

    def save(self, obj: PersistableModel) -> None: ...

    def ping(self) -> bool: ...

    def inbox_append(self, activity_id: str) -> None: ...

    def inbox_list(self) -> list[str]: ...

    def inbox_pop(self) -> str | None: ...

    def outbox_append(self, activity_id: str) -> None: ...

    def outbox_list(self) -> list[str]: ...

    def outbox_pop(self) -> str | None: ...

    def record_outbox_item(self, actor_id: str, activity_id: str) -> None: ...

    def by_type(self, type_: str) -> dict[str, dict[str, Any]]: ...

    def get_all(self, table: str) -> list[dict[str, Any]]: ...

    def all(
        self, table: str | None = None
    ) -> list[StorableRecord] | dict[str, PersistableModel]: ...

    def count_all(self) -> dict[str, int]: ...

    def find_actor_by_short_id(
        self, short_id: str
    ) -> PersistableModel | None: ...
