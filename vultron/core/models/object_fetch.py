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

"""Object dereference: what a receiver fetches, and the fetch it waits on.

A receiver that does not hold an object a received activity names fetches it
through an API call to whoever holds it, and defers the activity until the
object arrives (AKM-05-003, AKM-05-006, ADR-0107).  An
:class:`ObjectReference` names one object to fetch and where from; a
:class:`PendingObjectFetch` is the receiver's record of one outstanding or
settled fetch, and of the activities waiting on it.
"""

from __future__ import annotations

import urllib.parse
from enum import StrEnum
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from vultron.core.models.base import (
    CoreRecord,
    UriString,
    ValidatedAssignmentMixin,
    with_record_id,
)
from vultron.core.models.received_body import require_json_object_text
from vultron.primitives import NonEmptyString


class ObjectFetchSource(StrEnum):
    """Who serves the object a reference names."""

    #: The case's CASE_MANAGER, through its case-scoped object read.
    CASE_HOST = "case_host"
    #: The actor itself, through its published profile (AR-10-001).
    ACTOR_PROFILE = "actor_profile"


class ObjectFetchUse(StrEnum):
    """What the receiver does with an object once it is fetched."""

    #: Kept in the receiver's store, as a copy of the case host's record,
    #: so the replay rehydrates it like any held object.
    STORE = "store"
    #: Handed to the waiting activity alone and never stored, as the
    #: proposer's profile is (CP-01-010).
    HAND_OFF = "hand_off"


class ObjectFetchState(StrEnum):
    """Where one fetch stands."""

    PENDING = "pending"
    FETCHED = "fetched"
    FAILED = "failed"


class ObjectReference(ValidatedAssignmentMixin):
    """One object a receiver must fetch before it can process an activity.

    Attributes:
        object_id: The id the activity names the object by.
        source: Who serves it.
        host_actor_id: The actor the fetch is addressed to: the case's
            CASE_MANAGER for :attr:`ObjectFetchSource.CASE_HOST`, the actor
            itself for :attr:`ObjectFetchSource.ACTOR_PROFILE`.
        case_id: The case the object is read under; required for
            :attr:`ObjectFetchSource.CASE_HOST`.
        use: What the receiver does with the fetched object.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    object_id: UriString
    source: ObjectFetchSource
    host_actor_id: UriString
    case_id: UriString | None = None
    use: ObjectFetchUse

    @model_validator(mode="after")
    def _case_host_names_its_case(self) -> ObjectReference:
        """A case-host read is scoped to a case, so it must name one."""
        if self.source is ObjectFetchSource.CASE_HOST and self.case_id is None:
            raise ValueError(
                f"a case-host fetch of {self.object_id!r} names no case"
            )
        return self


class PendingObjectFetch(CoreRecord):
    """A receiver's record of one object fetch and the activities awaiting it.

    One record per object id, so a second activity naming an object already
    being fetched waits on the same fetch.  ``state`` moves from ``PENDING``
    to ``FETCHED`` (a :attr:`ObjectFetchUse.HAND_OFF` object, whose body the
    record keeps for the waiting activities) or ``FAILED`` (the bounded
    retries ran out, AKM-05-008).  A ``STORE`` fetch that succeeds leaves no
    record: the object is held, and that is all its waiters need.  A settled
    record is removed once no activity waits on it, so a later activity
    naming the object fetches it afresh.
    """

    type_: Literal["PendingObjectFetch"] = Field(  # type: ignore[assignment]
        default="PendingObjectFetch",
        validation_alias="type",
        serialization_alias="type",
    )
    object_id: UriString = Field(..., description="The object to fetch")
    source: ObjectFetchSource
    host_actor_id: UriString = Field(
        ..., description="The actor the fetch is addressed to"
    )
    case_id: UriString | None = Field(
        default=None, description="The case a case-host fetch reads under"
    )
    use: ObjectFetchUse
    waiting_activity_ids: list[UriString] = Field(
        default_factory=list,
        description="Held activities that replay once the fetch settles",
    )
    state: ObjectFetchState = ObjectFetchState.PENDING
    attempts: int = Field(
        default=0, ge=0, description="Fetch attempts made so far"
    )
    fetched_body: NonEmptyString | None = Field(
        default=None,
        description="The fetched JSON object, for a HAND_OFF fetch",
    )
    failure_reason: NonEmptyString | None = Field(
        default=None, description="Why the fetch failed, once it has"
    )

    @classmethod
    def build_id(cls, object_id: str) -> str:
        """Return the receiver's stable DataLayer id for *object_id*'s fetch."""
        slug = urllib.parse.quote(object_id, safe="")
        return f"pending-object-fetch/{slug}"

    @classmethod
    def for_reference(cls, reference: ObjectReference) -> PendingObjectFetch:
        """A new ``PENDING`` fetch of *reference*, awaited by nothing yet."""
        return cls(
            object_id=reference.object_id,
            source=reference.source,
            host_actor_id=reference.host_actor_id,
            case_id=reference.case_id,
            use=reference.use,
        )

    @property
    def reference(self) -> ObjectReference:
        """The reference this record fetches."""
        return ObjectReference(
            object_id=self.object_id,
            source=self.source,
            host_actor_id=self.host_actor_id,
            case_id=self.case_id,
            use=self.use,
        )

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from ``object_id``."""
        if isinstance(data, dict):
            object_id = data.get("object_id")
            if object_id is not None:
                data = with_record_id(data, cls.build_id(object_id))
        return data

    @model_validator(mode="after")
    def _state_matches_its_fields(self) -> PendingObjectFetch:
        """A fetched record holds its body; a failed one says why."""
        if self.fetched_body is not None:
            require_json_object_text(self.fetched_body, "fetched_body")
        if (self.state is ObjectFetchState.FETCHED) != (
            self.fetched_body is not None
        ):
            raise ValueError(
                f"fetch of {self.object_id!r}: a FETCHED record, and only"
                " one, carries the fetched body"
            )
        if (self.state is ObjectFetchState.FAILED) != (
            self.failure_reason is not None
        ):
            raise ValueError(
                f"fetch of {self.object_id!r}: a FAILED record, and only"
                " one, carries a failure reason"
            )
        if (
            self.state is ObjectFetchState.FETCHED
            and self.use is not ObjectFetchUse.HAND_OFF
        ):
            raise ValueError(
                f"fetch of {self.object_id!r}: only a HAND_OFF fetch keeps"
                " its fetched body; a STORE fetch stores the object"
            )
        return self


__all__ = [
    "ObjectFetchSource",
    "ObjectFetchState",
    "ObjectFetchUse",
    "ObjectReference",
    "PendingObjectFetch",
]
