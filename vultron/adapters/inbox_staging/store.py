"""The scratch store a delivery is staged in, and the rows it holds.

:class:`_StagingStore` is an in-memory store, emptied before and after each
use, that answers any read it does not hold from the receiver's own store.
"""

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

import threading
from dataclasses import dataclass
from typing import Any

from sqlmodel import select

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    VultronObjectRecord,
)
from vultron.adapters.driven.datalayer_sqlite.engine import scratch_memory_url
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import DataLayer, StorableRecord

#: Every actor's staging store is emptied around each use, so two uses must
#: never overlap.  The per-actor inbox lock already serialises a production
#: actor's deliveries; this lock also covers callers that run the pipeline
#: without it, as the tests do.
_STAGING_LOCK = threading.Lock()


class _StagingStore(SqliteDataLayer):
    """An in-memory store that reads through to the receiver's own store.

    Reads of anything but the activity being rebuilt go to *held* first, so
    an object the receiver already holds is always the one routing sees, as it
    was when ingress wrote inline objects and a duplicate was skipped.  The
    activity itself is read only from the copy staged here: the receiver holds
    none under its sender's id (DL-06-006), and the read that rebuilds it
    resolves its references through the store that returned it.
    """

    def __init__(self, held: DataLayer, activity_id: str) -> None:
        # Every SqliteDataLayer names its deployment and its actor; a store
        # that names neither still gets a staging store of its own.
        super().__init__(
            scratch_memory_url(
                getattr(held, "db_url", "sqlite:///:memory:"), "inbox-staging"
            ),
            actor_id=getattr(held, "actor_id", None) or "inbox-staging",
        )
        self._held = held
        self._activity_id = activity_id

    def read(
        self, object_id: str, raise_on_missing: bool = False
    ) -> PersistableModel | None:
        """Read from the receiver's store first, except for the activity."""
        if object_id != self._activity_id:
            held = self._held.read(object_id)
            if held is not None:
                return held
        return super().read(object_id, raise_on_missing)

    def staged_rows(
        self,
    ) -> tuple[dict[str, object] | None, list[dict[str, object]]]:
        """Return the activity's staged row and every other row staged here."""
        with self._session() as session:
            rows = session.exec(select(VultronObjectRecord)).all()
            as_dicts: list[dict[str, object]] = [
                {"id_": row.id_, "type_": row.type_, "data_": row.data}
                for row in rows
            ]
        own = [row for row in as_dicts if row["id_"] == self._activity_id]
        inline = [row for row in as_dicts if row["id_"] != self._activity_id]
        return (own[0] if own else None), inline


def _row_record(row: dict[str, Any]) -> StorableRecord:
    """A held storage row, as the record ``create`` accepts."""
    return StorableRecord(
        id_=str(row["id_"]), type_=str(row["type_"]), data_=row["data_"]
    )


@dataclass(frozen=True)
class _Staged:
    """What one rebuild staged, kept so a deferral can hold it."""

    received_body: str | None
    inline_rows: list[dict[str, object]]
