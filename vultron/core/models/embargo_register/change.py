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


"""One embargo's change within a register step, and register-wide checks (ADR-0122).

The register is the case's ordered list of embargoes, each storing its own
``status``, ``replaces`` and ``termination`` (ADR-0202).
"""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, model_validator

from vultron.core.models.base import (
    NonEmptyString,
    ValidatedAssignmentMixin,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    RegisterTrigger,
)

_S = EmbargoRegisterStatus
_T = RegisterTrigger


class RegisterChange(ValidatedAssignmentMixin, BaseModel):
    """One embargo's trigger within a register step."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    embargo_id: NonEmptyString
    trigger: RegisterTrigger
    #: ``PROPOSE`` only, and required there: the embargo the register adds.
    #: The register holds each embargo whole, since its status is stored on
    #: it (ADR-0202).
    embargo: EmbargoEvent | None = None
    #: ``TERMINATE`` only, and required there: how the embargo ended, stored
    #: on the ``TERMINATED`` embargo (ADR-0202).
    termination: EmbargoTermination | None = None

    @model_validator(mode="after")
    def _trigger_fields_agree(self) -> RegisterChange:
        """Refuse a termination or embargo object the trigger cannot carry (EH-07-001)."""
        problems: list[str] = []
        if (self.termination is None) == (self.trigger == _T.TERMINATE):
            problems.append(
                "a termination is required on TERMINATE and refused otherwise"
            )
        if (self.embargo is None) == (self.trigger == _T.PROPOSE):
            problems.append(
                "the embargo object is required on PROPOSE and refused"
                " otherwise"
            )
        if self.embargo is not None and self.embargo.id_ != self.embargo_id:
            problems.append("PROPOSE carries the embargo under its own id")
        if problems:
            raise ValueError(
                f"Register change '{self.trigger}' on '{self.embargo_id}': "
                + "; ".join(problems)
            )
        return self


def repeated_ids(ids: Sequence[str]) -> list[str]:
    """The ids that occur more than once in *ids*, sorted."""
    return sorted({i for i in ids if ids.count(i) > 1})


def replaces_violations(embargoes: Sequence[EmbargoEvent]) -> list[str]:
    """Every ``replaces`` link in *embargoes* that names no embargo or loops.

    Reading lapsed (ADR-0122) follows ``replaces`` back from the ``ACTIVE``
    embargo, so each link must name an embargo the register holds, and the
    chain from any embargo must end rather than come back on itself.
    """
    by_id = {embargo.id_: embargo for embargo in embargoes}
    violations: list[str] = []
    for embargo in embargoes:
        if embargo.replaces is not None and embargo.replaces not in by_id:
            violations.append(
                f"'{embargo.id_}' replaces '{embargo.replaces}', which the"
                " register does not hold"
            )
    looped: set[str] = set()
    for embargo in embargoes:
        seen = {embargo.id_}
        replaced_id = embargo.replaces
        while replaced_id is not None and replaced_id in by_id:
            if replaced_id in seen:
                looped.add(embargo.id_)
                break
            seen.add(replaced_id)
            replaced_id = by_id[replaced_id].replaces
    if looped:
        violations.append(
            f"the replaces chain from {sorted(looped)} comes back on itself"
        )
    return violations
