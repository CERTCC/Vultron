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
"""The answer a call-out backend gives, and the declaration it answers against.

Every call-out backend gives one :class:`CallOutAnswer`: exactly one
:class:`CallOutVerdict` (*yes*, *no* or *error*) and the data its capability
declares for that verdict (ADR-0183):

- *yes* carries the capability's declared outputs;
- *no* carries a refusal payload: a human-readable reason at minimum, plus any
  structured refusal fields the capability declares;
- *error* carries diagnostics for the raised error and the logs, never for the
  blackboard.

A :class:`CallOutContract` is the capability declaration the seam checks an
answer against.  It names the output ports written on *yes* and the refusal
ports written on *no*.  A new kind of data extends a declaration, never the
verdict vocabulary.

Each verdict writes only its own ports, and nothing clears the other
verdict's ports, so a port read after an earlier tick may hold that tick's
value.  A reader trusts a port only on the branch of its own verdict: an
output after the node succeeded, a refusal port after it failed.

The seam (:class:`~vultron.core.behaviors.call_out.guard.SynchronousCallOut`)
is the only place that interprets an answer; no tree reads one.

References
----------
- ADR-0183: ``docs/adr/0183-a-call-out-backend-answers-yes-no-or-error-and-the-seam-turns-the-answer-into-tree-behaviour.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-001, BT-18-002,
  BT-18-007
- Notes: ``notes/call-out-configuration.md``
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vultron.primitives import NonEmptyString, require_non_empty

#: Blackboard key the seam writes a refusal reason to when a capability does
#: not name its own.  A capability whose reason a tree or record reads names
#: its own key, so another call-out point's refusal never overwrites it.
REFUSAL_REASON_KEY: Final[str] = "call_out_refusal_reason"


class CallOutVerdict(StrEnum):
    """The fixed verdict vocabulary of a call-out answer (ADR-0183)."""

    YES = "yes"
    """The backend decided, fetched or acted: the node succeeds."""

    NO = "no"
    """The backend decided against: the node fails.  Only for a decision."""

    ERROR = "error"
    """The backend could not decide or act: the seam raises, nothing is judged."""


def is_of_port_type(value: object, port_type: type) -> bool:
    """Whether *value* is of a declared port's *port_type*.

    ``isinstance``, except that a ``bool`` is not an ``int``: Python makes
    ``bool`` a subclass of ``int``, so a plain check would let ``True``
    through on an ``int`` port, and a mismatch would go unseen
    (BTND-03-021).
    """
    if port_type is int and isinstance(value, bool):
        return False
    return isinstance(value, port_type)


@dataclass(frozen=True)
class CallOutContract:
    """A capability's declaration of the data each verdict carries.

    Attributes:
        outputs: Output ports written on *yes*, as blackboard key → type.  A
            binary capability declares none (BT-18-010).  Each type is a
            plain class: the seam checks every value with ``isinstance``.
        refusal_reason_key: Blackboard key the *no* reason is written to.
        refusal_fields: Structured refusal ports written on *no* beside the
            reason, as blackboard key → type.
    """

    outputs: Mapping[str, type] = field(
        default_factory=lambda: MappingProxyType({})
    )
    refusal_reason_key: str = REFUSAL_REASON_KEY
    refusal_fields: Mapping[str, type] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        # Frozen dataclass: freeze the mappings without a second field.
        object.__setattr__(
            self, "outputs", MappingProxyType(dict(self.outputs))
        )
        object.__setattr__(
            self,
            "refusal_fields",
            MappingProxyType(dict(self.refusal_fields)),
        )
        require_non_empty(self.refusal_reason_key, "refusal_reason_key")
        for key, typ in (*self.outputs.items(), *self.refusal_fields.items()):
            # The seam checks each value with isinstance(), which a generic
            # alias, a union or Any cannot answer, so such a port would let
            # any value through (BT-18-036).
            if not isinstance(typ, type) or typ is Any:
                raise ValueError(
                    f"port {key!r} declares {typ!r}, not a plain class; a "
                    "declared port type is a class the seam can check a "
                    "value against"
                )
        if self.refusal_reason_key in self.refusal_fields:
            raise ValueError(
                f"refusal field {self.refusal_reason_key!r} repeats the "
                "refusal reason key"
            )
        if overlap := sorted(set(self.outputs) & set(self.refusal_ports)):
            raise ValueError(
                f"ports {overlap} are declared both as outputs and as "
                "refusal ports; a key belongs to one verdict"
            )

    @property
    def refusal_ports(self) -> Mapping[str, type]:
        """Every port written on *no*: the reason, then the declared fields."""
        return MappingProxyType(
            {self.refusal_reason_key: str, **self.refusal_fields}
        )


#: The declaration of a capability with no outputs and only a reason on *no*.
BINARY_CONTRACT: Final[CallOutContract] = CallOutContract()


class CallOutAnswer(BaseModel):
    """One answer from a call-out backend: a verdict and its data (ADR-0183).

    Build one with :meth:`yes`, :meth:`no` or :meth:`error`.  The model
    refuses data that belongs to another verdict, so an answer always
    carries exactly its own verdict's data; the seam then checks that data
    against the capability's :class:`CallOutContract`.

    Attributes:
        verdict: Exactly one of *yes*, *no* or *error*.
        outputs: The *yes* outputs, by blackboard key.
        reason: The *no* reason; required on *no*, absent otherwise.
        refusal: The *no* structured refusal fields, by blackboard key.
        diagnostics: The *error* diagnostics; required on *error*, absent
            otherwise.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    verdict: CallOutVerdict
    outputs: dict[str, object] = Field(default_factory=dict)
    reason: NonEmptyString | None = None
    refusal: dict[str, object] = Field(default_factory=dict)
    diagnostics: NonEmptyString | None = None

    @model_validator(mode="after")
    def _data_matches_verdict(self) -> Self:
        if self.verdict is not CallOutVerdict.YES and self.outputs:
            raise ValueError(f"a {self.verdict} answer carries no outputs")
        if self.verdict is CallOutVerdict.NO:
            if self.reason is None:
                raise ValueError("a no answer carries a reason")
        elif self.reason is not None or self.refusal:
            raise ValueError(
                f"a {self.verdict} answer carries no refusal payload"
            )
        if self.verdict is CallOutVerdict.ERROR:
            if self.diagnostics is None:
                raise ValueError("an error answer carries diagnostics")
        elif self.diagnostics is not None:
            raise ValueError(f"a {self.verdict} answer carries no diagnostics")
        return self

    @classmethod
    def yes(cls, outputs: Mapping[str, object] | None = None) -> CallOutAnswer:
        """Answer *yes*, with the capability's declared outputs."""
        return cls(verdict=CallOutVerdict.YES, outputs=dict(outputs or {}))

    @classmethod
    def no(
        cls, reason: str, refusal: Mapping[str, object] | None = None
    ) -> CallOutAnswer:
        """Answer *no* for a decision, with its reason and refusal fields."""
        return cls(
            verdict=CallOutVerdict.NO,
            reason=reason,
            refusal=dict(refusal or {}),
        )

    @classmethod
    def error(cls, diagnostics: str) -> CallOutAnswer:
        """Answer *error*: the backend could not decide or act."""
        return cls(verdict=CallOutVerdict.ERROR, diagnostics=diagnostics)


__all__ = [
    "BINARY_CONTRACT",
    "CallOutAnswer",
    "CallOutContract",
    "CallOutVerdict",
    "REFUSAL_REASON_KEY",
    "is_of_port_type",
]
