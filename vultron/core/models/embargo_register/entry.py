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


"""One embargo register entry and one change to it (ADR-0122)."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from vultron.core.models._helpers import _as_id
from vultron.core.models.base import (
    NonEmptyString,
    PropertyValueKind,
    ValidatedAssignmentMixin,
    vultron_property,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    RegisterTrigger,
)

_S = EmbargoRegisterStatus
_T = RegisterTrigger


#: Statuses an entry reaches only by having been ``ACTIVE``.
_WAS_ACTIVE = frozenset({_S.ACTIVE, _S.SUPERSEDED, _S.TERMINATED})


class EmbargoRegisterEntry(ValidatedAssignmentMixin, BaseModel):
    """One embargo in a case's register: ``(embargo, status, replaces)``.

    ``embargo`` is the ``EmbargoEvent`` or its id.  The object form is kept
    when a sender carried it, so a recipient can read the terms of the
    embargo in force without a dereference (AKM-02-004, DL-08-001).
    ``replaces`` names the embargo an activated revision replaced.
    ``termination`` is how a ``TERMINATED`` entry ended — the what and, when
    recorded, the why (ADR-0122) — and is set on that status only.  Entries
    are frozen: they change only by :func:`apply_register_step`.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )

    embargo: NonEmptyString | EmbargoEvent = Field(
        json_schema_extra=vultron_property(
            (
                "The embargo an embargo-register entry records: an "
                "EmbargoEvent or its id"
            ),
            PropertyValueKind.IRI,
        )
    )
    status: EmbargoRegisterStatus = Field(
        json_schema_extra=vultron_property(
            (
                "The status of an embargo in its case's embargo register, "
                "such as PROPOSED, ACTIVE or TERMINATED"
            ),
            PropertyValueKind.PLAIN,
        )
    )
    replaces: NonEmptyString | None = Field(
        default=None,
        json_schema_extra=vultron_property(
            "The id of the embargo that an activated revision replaced",
            PropertyValueKind.IRI,
        ),
    )
    termination: EmbargoTermination | None = Field(
        default=None,
        json_schema_extra=vultron_property(
            (
                "How a terminated embargo ended: an object that gives the "
                "reason and, when recorded, its cause"
            ),
            PropertyValueKind.PLAIN,
        ),
    )

    @model_validator(mode="after")
    def _status_fields_agree(self) -> EmbargoRegisterEntry:
        """Refuse a ``replaces`` or ``termination`` the status cannot carry."""
        problems: list[str] = []
        if (self.termination is None) == (self.status == _S.TERMINATED):
            problems.append(
                "a termination is required on a TERMINATED entry and refused"
                " otherwise"
            )
        if self.replaces is not None and self.status not in _WAS_ACTIVE:
            problems.append(
                f"replaces is set on a {self.status} entry, which was never"
                " activated"
            )
        if self.replaces is not None and self.replaces == self.embargo_id:
            problems.append("an entry cannot replace itself")
        if problems:
            raise ValueError(
                f"Embargo register entry '{self.embargo_id}': "
                + "; ".join(problems)
            )
        return self

    @property
    def embargo_id(self) -> str:
        """The id of the embargo this entry is for."""
        embargo_id = _as_id(self.embargo)
        assert embargo_id is not None  # NonEmptyString or an object with id_
        return embargo_id


class RegisterChange(ValidatedAssignmentMixin, BaseModel):
    """One entry's trigger within a register step."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    embargo_id: NonEmptyString
    trigger: RegisterTrigger
    #: ``PROPOSE`` only: the embargo object, kept inline on the new entry.
    embargo: EmbargoEvent | None = None
    #: ``TERMINATE`` only, and required there: how the embargo ended, stored
    #: on the ``TERMINATED`` entry.  A replica that learned the termination
    #: from a ``Remove`` knows only its what (ADR-0122, #4294).
    termination: EmbargoTermination | None = None

    @model_validator(mode="after")
    def _trigger_fields_agree(self) -> RegisterChange:
        """Refuse a termination or embargo object the trigger cannot carry (EH-07-001)."""
        problems: list[str] = []
        if (self.termination is None) == (self.trigger == _T.TERMINATE):
            problems.append(
                "a termination is required on TERMINATE and refused otherwise"
            )
        if self.embargo is not None and (
            self.trigger != _T.PROPOSE or self.embargo.id_ != self.embargo_id
        ):
            problems.append(
                "only PROPOSE carries the embargo object, under its own id"
            )
        if problems:
            raise ValueError(
                f"Register change '{self.trigger}' on '{self.embargo_id}': "
                + "; ".join(problems)
            )
        return self


def repeated_ids(ids: Sequence[str]) -> list[str]:
    """The ids that occur more than once in *ids*, sorted."""
    return sorted({i for i in ids if ids.count(i) > 1})


def replaces_violations(entries: Sequence[EmbargoRegisterEntry]) -> list[str]:
    """Every ``replaces`` link in *entries* that names no entry or loops.

    Reading lapsed (ADR-0122) follows ``replaces`` back from the ``ACTIVE``
    entry, so each link must name an entry the register holds, and the
    chain from any entry must end rather than come back on itself.
    """
    by_id = {entry.embargo_id: entry for entry in entries}
    violations: list[str] = []
    for entry in entries:
        if entry.replaces is not None and entry.replaces not in by_id:
            violations.append(
                f"'{entry.embargo_id}' replaces '{entry.replaces}', which the"
                " register holds no entry for"
            )
    looped: set[str] = set()
    for entry in entries:
        seen = {entry.embargo_id}
        replaced_id = entry.replaces
        while replaced_id is not None and replaced_id in by_id:
            if replaced_id in seen:
                looped.add(entry.embargo_id)
                break
            seen.add(replaced_id)
            replaced_id = by_id[replaced_id].replaces
    if looped:
        violations.append(
            f"the replaces chain from {sorted(looped)} comes back on itself"
        )
    return violations
