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

"""The generic base of every core trigger request.

:class:`TriggerRequest` adds ``actor_id`` to a request body and binds the
:class:`TriggerResult` subtype its verb returns; :func:`result_type_of`
recovers that binding at runtime.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from vultron.core.models.base import NonEmptyString
from vultron.core.models.use_case_result import (
    TriggerResult,
)

ResultT_co = TypeVar("ResultT_co", bound=TriggerResult, covariant=True)


# ADR-0110 exports ResultT_co for callers to import; a PEP 695 parameter is
# class-scoped and could not be.
class TriggerRequest(BaseModel, Generic[ResultT_co]):  # noqa: UP046
    """Base of every trigger use-case request: ``actor_id`` plus a result type.

    Concrete requests bind ``ResultT_co`` to the :class:`TriggerResult`
    subtype their verb's use case returns and mix in the verb's body model,
    which carries every other field.  The type parameter is phantom — no field
    is typed with it — so it costs nothing at validation time and exists for
    the static binding between a request and its result.
    """

    model_config = ConfigDict(extra="ignore")

    actor_id: NonEmptyString


def result_type_of(
    request_cls: type[TriggerRequest[Any]],
) -> type[TriggerResult]:
    """Return the :class:`TriggerResult` subtype *request_cls* is bound to.

    Walks the MRO for the parametrised ``TriggerRequest[...]`` base pydantic
    recorded and returns its argument.  Raises ``TypeError`` for a request
    class that never bound one — every concrete request MUST.
    """
    for klass in request_cls.__mro__:
        metadata = getattr(klass, "__pydantic_generic_metadata__", None)
        if (
            metadata
            and metadata.get("origin") is TriggerRequest
            and metadata.get("args")
        ):
            bound = metadata["args"][0]
            if isinstance(bound, type) and issubclass(bound, TriggerResult):
                return bound
    raise TypeError(
        f"{request_cls.__name__} does not bind a TriggerResult subtype"
    )
