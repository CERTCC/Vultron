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

"""Narrow outbound port for core domain use cases and BT nodes.

:class:`CasePersistence` covers the methods called by
``vultron/core/`` use cases — excluding inbox/outbox queues, health,
diagnostics, and low-level storage primitives (``update``, ``delete``,
``clear_*``, ``count_all``) that belong to the adapter layer.

:class:`CaseOutboxPersistence` is defined in
``vultron/core/ports/case_outbox`` and re-exported here for backward
compatibility.

``SqliteDataLayer`` satisfies both Protocols structurally with no declaration
needed (Python structural subtyping).

See also:
    - ``specs/datalayer.yaml`` DL-03-001, DL-03-002
    - ``vultron/core/ports/case_outbox.py`` for :class:`CaseOutboxPersistence`
    - GitHub issue #403
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol

from vultron.core.models.protocols import PersistableModel
from vultron.core.models.protocol_pair import ProtocolPair
from vultron.core.ports.datalayer import StorableRecord

if TYPE_CHECKING:
    from vultron.core.models.case import VulnerabilityCase


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
        """The canonical URI of the actor whose store this is (ADR-0073).

        Implementations MUST return a non-empty string URI and MUST NOT raise
        ``NotImplementedError``.  Callers such as ``resolve_receiving_actor_id``
        treat a missing or non-string value as "no actor available" and raise
        ``VultronValidationError`` — but they do not catch ``NotImplementedError``,
        which is reserved as an unambiguous signal that the adapter is incomplete
        (CM-01-001).
        """
        ...

    def clone_for_actor(self, actor_id: str) -> "CasePersistence":
        """Return the store belonging to *actor_id*.

        The only way to reach a store other than this one, and deliberately
        explicit: ADR-0073 makes cross-actor access something a caller must
        name rather than something a forgotten filter grants by accident.
        """
        ...

    def create(self, record: "StorableRecord | PersistableModel") -> None: ...

    def read(
        self, object_id: str, raise_on_missing: bool = False
    ) -> PersistableModel | None: ...

    def read_case(
        self, case_id: str, raise_on_missing: bool = False
    ) -> "VulnerabilityCase | None": ...

    def save(self, obj: PersistableModel) -> None: ...

    def save_many(self, objs: list[PersistableModel]) -> None: ...

    def list_objects(self, type_key: str) -> Iterable[PersistableModel]: ...

    def find_case_by_report_id(
        self, report_id: str
    ) -> "VulnerabilityCase | None": ...

    def find_actor_by_short_id(
        self, short_id: str
    ) -> PersistableModel | None: ...

    def find_case_by_short_id(
        self, short_id: str
    ) -> "VulnerabilityCase | None": ...

    def find_protocol_pair(
        self,
        case_id: str,
        request_event_type: str,
        object_id: str,
        reply_event_types: frozenset[str],
    ) -> ProtocolPair: ...

    def delete(self, table: str, id_: str) -> bool: ...


# Re-export CaseOutboxPersistence for backward compatibility.
# CaseOutboxPersistence is now the canonical definition; existing callers of
# `from vultron.core.ports.case_persistence import CaseOutboxPersistence`
# continue to work without changes.
#
# The __getattr__ pattern (PEP 562) is used rather than a direct module-level
# import to avoid a circular dependency: case_outbox imports CasePersistence
# from this module, so a top-level `from case_outbox import ...` here would
# form a cycle that breaks when case_outbox.py is loaded first.
if TYPE_CHECKING:
    from vultron.core.ports.case_outbox import (
        CaseOutboxPersistence,
    )  # noqa: F401

__all__ = ["CasePersistence", "CaseOutboxPersistence"]


def __getattr__(name: str) -> type:
    if name == "CaseOutboxPersistence":
        from vultron.core.ports.case_outbox import (
            CaseOutboxPersistence,
        )  # noqa: F811

        globals()[name] = CaseOutboxPersistence
        return CaseOutboxPersistence
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
