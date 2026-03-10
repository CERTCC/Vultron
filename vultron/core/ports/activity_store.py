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

"""
DataLayer port — the storage interface used by the core domain layer.

Concrete implementations (e.g. ``TinyDbDataLayer``) live in the adapter
layer at ``vultron/api/v2/datalayer/`` and import this Protocol to
verify structural conformance.

No adapter-layer types (``Record``, ``TinyDB``, etc.) appear here.
"""

from typing import Any, Protocol

from pydantic import BaseModel


class DataLayer(Protocol):
    """Protocol for a data layer.

    Defines the minimum interface that any concrete storage adapter must
    satisfy.  Method parameters use ``Any`` so that the core layer
    remains decoupled from the specific record wrapper used by the adapter
    (e.g. ``Record`` in TinyDB).  Callers that need stronger typing should
    rely on the concrete implementation.
    """

    def create(self, record: Any) -> None: ...

    def read(self, object_id: str) -> BaseModel | None: ...

    def get(self, table: str | None, id_: str | None) -> Any: ...

    def update(self, id_: str, record: Any) -> None: ...

    def delete(self, table: str, id_: str) -> None: ...

    def clear_table(self, table: str) -> None: ...

    def clear_all(self) -> None: ...
