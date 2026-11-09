#!/usr/bin/env python
"""
Provides the base class for all Vultron ActivityStreams activity wire types.
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

from typing import Any, ClassVar, Self

from pydantic import model_validator

from vultron.core.models.activity import VultronActivity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)


class as_VultronActivity(as_TransitiveActivity):
    """Base class for Vultron ActivityStreams activity wire types.

    Provides a generic :meth:`from_core` classmethod that converts a
    :class:`~vultron.core.models.activity.VultronActivity` domain object into
    its wire representation via a JSON round-trip::

        data = domain_activity.model_dump(mode="json")
        # apply _field_map renames (domain key → wire key)
        return cls.model_validate(data)

    The wire base accepts both Python attribute names and JSON alias names on
    validation (``validate_by_name=True`` on :class:`as_Base`), so the
    Python-keyed dump from the domain model passes through cleanly.

    **``_field_map`` contract**: When a concrete subclass wire type uses
    different field names than the corresponding domain type, declare the
    mapping as::

        _field_map: ClassVar[dict[str, str]] = {"domain_field": "wire_field"}

    The default :meth:`from_core` applies these renames before calling
    :func:`~pydantic.BaseModel.model_validate`.  Most activity types need no
    renames and can inherit the default without override.

    Subclasses SHOULD narrow the ``domain_activity`` parameter type, e.g.::

        @classmethod
        def from_core(
            cls, domain_activity: VultronCreateCaseActivity
        ) -> "CreateCaseActivity":
            return super().from_core(domain_activity)
    """

    _field_map: ClassVar[dict[str, str]] = {}

    @classmethod
    def from_core(
        cls, domain_activity: VultronActivity
    ) -> "as_VultronActivity":
        """Create a wire activity from a core domain activity.

        Performs a JSON round-trip: dumps the domain object with Python field
        names, applies any ``_field_map`` renames, then validates against the
        wire type.

        Args:
            domain_activity: A :class:`VultronActivity` domain model instance.

        Returns:
            A new instance of this wire activity type populated from
            ``domain_activity``.
        """
        data: dict[str, Any] = domain_activity.model_dump(mode="json")
        for domain_field, wire_field in cls._field_map.items():
            if domain_field in data:
                data[wire_field] = data.pop(domain_field)
        return cls.model_validate(data)


def reply_to_object(reply: Any) -> None:
    """Set *reply*'s ``in_reply_to`` to its ``object_``'s id when unset.

    The rule of every response whose ``object`` is the activity it answers,
    such as ``Accept(Offer(...))`` or ``Reject(Invite(...))`` (RF-08-001,
    RF-08-002).  A sender that names another antecedent, such as the
    original recommender's Offer, keeps its own value.
    """
    if reply.in_reply_to is None:
        object.__setattr__(reply, "in_reply_to", reply.object_.id_)


class RepliesToObject:
    """Mixin: a response whose ``object`` is the activity it answers.

    Put it before the ``as_Accept``, ``as_Reject`` or ``as_TentativeReject``
    base.  Its ``model_validator`` applies :func:`reply_to_object`, so no
    such response is built without ``inReplyTo`` (RF-08-002, RF-08-003).
    """

    @model_validator(mode="after")
    def _reply_to_object(self) -> Self:
        reply_to_object(self)
        return self
