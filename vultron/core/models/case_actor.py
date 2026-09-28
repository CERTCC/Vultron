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

"""Domain representations for CaseActor and its outbox."""

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, model_validator

from vultron.core.models.base import CoreObject, ValidatedAssignmentMixin
from vultron.core.models.enums import VultronActorType


class VultronOutbox(ValidatedAssignmentMixin, BaseModel):
    """Minimal outbox representation for domain actor types."""

    items: list[str] = Field(default_factory=list)


class CaseActor(CoreObject):
    """Domain representation of a CaseActor service.

    Mirrors the Vultron-specific fields of ``CaseActor`` (which inherits
    ``as_Service``).  The ``outbox`` field carries the actor's outgoing
    activity IDs and is required so that ``UpdateActorOutbox`` can append
    to it via ``datalayer.save``.

    ``type_`` is ``"Service"`` to match ``CaseActor``'s wire value, which
    means this class registers in :data:`CORE_VOCABULARY` under the key
    ``"CaseActor"`` (``cls.__name__``), not ``"Service"``.  DataLayer
    reconstitution still routes through the wire :data:`VOCABULARY` for
    ``"Service"`` objects; core ``CaseActor`` is used when constructing
    domain objects directly.  See ADR-0017 and issue #729.

    On the AS2 path the internal ``outbox`` is replaced by the actor's
    ``inbox``/``outbox`` collection URIs, derived from its id, which is what the
    deleted ``as_CaseActor.from_core`` did: a recipient needs the inbox to
    address the CaseActor, and AS2 defines ``outbox`` as a collection, not this
    class's tracking list.
    """

    local_only_fields: ClassVar[frozenset[str]] = frozenset({"outbox"})

    type_: Literal[VultronActorType.SERVICE] = Field(
        default=VultronActorType.SERVICE,
        validation_alias="type",
        serialization_alias="type",
    )
    outbox: VultronOutbox = Field(default_factory=VultronOutbox)

    @model_validator(mode="before")
    @classmethod
    def _accept_as2_collections(cls, data: Any) -> Any:
        """Read back the AS2 form :meth:`_as2_derived_fields` emits.

        The collection URIs are derived, not stored, so ``inbox`` is dropped and
        an ``outbox`` given as a URI or collection (rather than this class's
        tracking list) reads as an empty one.
        """
        if not isinstance(data, dict):
            return data
        outbox = data.get("outbox")
        if "inbox" not in data and not isinstance(outbox, str):
            return data
        data = dict(data)
        data.pop("inbox", None)
        if isinstance(outbox, str) or (
            isinstance(outbox, dict) and "items" not in outbox
        ):
            data.pop("outbox")
        return data

    def _as2_derived_fields(self) -> dict[str, Any]:
        return {"inbox": f"{self.id_}/inbox", "outbox": f"{self.id_}/outbox"}
