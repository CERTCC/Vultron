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
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

# Copyright

"""
Provides an abstract base class for a data layer. This is intended to define
the interface that concrete data layer implementations must follow.
"""
from typing import Protocol

from vultron.api.v2.datalayer.db_record import Record


class DataLayer(Protocol):
    """Protocol for a data layer."""

    def create(self, record: Record) -> None: ...

    def get(self, table: str, id_: str) -> Record | None: ...

    def update(self, id_: str, record: Record) -> None: ...

    def delete(self, table: str, id_: str) -> None: ...

    def all(self, table: str) -> list[Record]: ...

    def clear_table(self, table: str) -> None: ...

    def clear_all(self) -> None: ...
