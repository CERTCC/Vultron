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

"""Protocol types for structural contracts at DataLayer port boundaries.

Only Protocols that cannot be replaced by concrete ``isinstance`` checks
belong here. The duck-typing workaround Protocols (``CaseModel``,
``ParticipantModel``, ``ParticipantStatusModel``, ``LogEntryModel``) were
removed in favour of direct ``isinstance`` checks against core domain classes
(ADR-0034, DL-05-003).
"""

from typing import Any, Mapping, Protocol, TypeGuard

from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM


class PersistableModel(Protocol):
    @property
    def id_(self) -> str: ...

    @property
    def type_(self) -> str: ...

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...

    def model_copy(
        self, *, update: Mapping[str, Any] | None = None, deep: bool = False
    ) -> "PersistableModel": ...


class CaseStatusModel(Protocol):
    em_state: EM
    pxa_state: CS_pxa


class OutboxCollectionModel(Protocol):
    items: list[object]


class ActorModel(PersistableModel, Protocol):
    inbox: OutboxCollectionModel
    outbox: OutboxCollectionModel


def has_outbox(obj: PersistableModel | None) -> TypeGuard[ActorModel]:
    return bool(obj is not None and hasattr(obj, "outbox"))
