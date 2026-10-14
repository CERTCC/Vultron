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

"""The embargo register: one entry for every embargo proposed on a case.

``VulnerabilityCase.embargo_register`` is append-only (ADR-0122): an entry is
added by ``PROPOSE`` and changes status by the other triggers of
:mod:`vultron.core.states.embargo_register`, and is never removed.  Every
change is a **step** — the whole change one protocol event causes — and
:func:`apply_register_step` checks the step's triggers together against the
register invariants, so ``TERMINATE`` and the ``CANCEL`` of every open
proposal, or ``ACTIVATE`` and the ``SUPERSEDE`` it implies, are one change.
Each step names one EM trigger (:func:`register_step_em_trigger`), and the EM
derived before and after it must be one of that trigger's moves in
:data:`vultron.core.states.em.EM_TRANSITIONS` (ADR-0130).

The ``*_changes`` builders name the step each protocol event causes, so the
callers say *what happened* and the register decides which entries move.
"""

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.alias_generators import to_camel

from vultron.core.models._helpers import _as_id
from vultron.core.models.base import NonEmptyString, ValidatedAssignmentMixin
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.states.em import EM_Trigger, is_em_transition
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    RegisterTrigger,
    derive_em,
    register_invariant_violations,
    register_status_after,
)
from vultron.errors import VultronInvalidStateTransitionError

_S = EmbargoRegisterStatus
_T = RegisterTrigger

#: The EM trigger each register trigger belongs to (ADR-0130).  ``CANCEL`` is
#: absent: it is part of ``terminate`` beside a ``TERMINATE``, and ``reject``
#: alone, on a threat signal with no embargo in force (EMB-16-001).
_EM_TRIGGER_OF: Mapping[RegisterTrigger, EM_Trigger] = MappingProxyType(
    {
        _T.PROPOSE: EM_Trigger.PROPOSE,
        _T.ACTIVATE: EM_Trigger.ACCEPT,
        _T.SUPERSEDE: EM_Trigger.ACCEPT,
        _T.REJECT: EM_Trigger.REJECT,
        _T.TERMINATE: EM_Trigger.TERMINATE,
    }
)

#: Statuses an entry reaches only by having been ``ACTIVE``.
_WAS_ACTIVE = frozenset({_S.ACTIVE, _S.SUPERSEDED, _S.TERMINATED})


class EmbargoRegisterEntry(ValidatedAssignmentMixin, BaseModel):
    """One embargo in a case's register: ``(embargo, status, replaces)``.

    ``embargo`` is the ``EmbargoEvent`` or its id.  The object form is kept
    when a sender carried it, so a recipient can read the terms of the
    embargo in force without a dereference (AKM-03-001, DL-08-001).
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

    embargo: NonEmptyString | EmbargoEvent
    status: EmbargoRegisterStatus
    replaces: NonEmptyString | None = None
    termination: EmbargoTermination | None = None

    @model_validator(mode="after")
    def _status_fields_agree(self) -> "EmbargoRegisterEntry":
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
    def _trigger_fields_agree(self) -> "RegisterChange":
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


def _em_triggers_of(changes: Sequence[RegisterChange]) -> set[EM_Trigger]:
    """The EM triggers *changes* belong to; one for a well-formed step."""
    triggers = {change.trigger for change in changes}
    unmapped = triggers - set(_EM_TRIGGER_OF) - {_T.CANCEL}
    if unmapped:
        raise VultronInvalidStateTransitionError(
            "Embargo register: no EM trigger is mapped for"
            f" {sorted(t.name for t in unmapped)} (ADR-0130)."
        )
    em_triggers = {_EM_TRIGGER_OF[t] for t in triggers if t != _T.CANCEL}
    if _T.CANCEL in triggers:
        em_triggers.add(
            EM_Trigger.TERMINATE
            if _T.TERMINATE in triggers
            else EM_Trigger.REJECT
        )
    return em_triggers


def register_step_em_trigger(
    changes: Sequence[RegisterChange],
) -> EM_Trigger:
    """The EM trigger the register step *changes* is (ADR-0130).

    ``PROPOSE`` is ``propose``; ``ACTIVATE``, with any ``SUPERSEDE``, is
    ``accept``; ``REJECT`` is ``reject``; ``TERMINATE``, with any
    ``CANCEL``, is ``terminate``; and ``CANCEL`` alone — a threat signal
    abandoning open proposals with no embargo in force — is ``reject``.

    Raises:
        VultronInvalidStateTransitionError: the step changes nothing,
            mixes register triggers of more than one EM trigger, or carries
            a register trigger no EM trigger is mapped for.
    """
    em_triggers = _em_triggers_of(changes)
    if len(em_triggers) != 1:
        raise VultronInvalidStateTransitionError(
            "Embargo register: a step must name exactly one EM trigger, but"
            f" {[(c.trigger.name, c.embargo_id) for c in changes]} names"
            f" {sorted(str(t) for t in em_triggers) or 'none'}."
        )
    return em_triggers.pop()


def em_move_violations(
    before: Sequence[EmbargoRegisterEntry],
    after: Sequence[EmbargoRegisterEntry],
    em_trigger: EM_Trigger,
) -> list[str]:
    """The EM move from *before* to *after*, if *em_trigger* does not allow it.

    Both registers must keep invariants 1–3, so EM derives from each
    (ADR-0122); the move must then be in the EM transition table
    (ADR-0130, EMB-18-006).  An empty list means the move is legal.
    """
    source = derive_em(entry.status for entry in before)
    dest = derive_em(entry.status for entry in after)
    if is_em_transition(em_trigger, source, dest):
        return []
    return [
        f"EM {source} → {dest} is not an EM transition for"
        f" '{em_trigger}' (ADR-0130)"
    ]


def _step_violations(
    entries: Sequence[EmbargoRegisterEntry],
    changes: Sequence[RegisterChange],
    *,
    threat_signal: bool,
) -> list[str]:
    """Every rule the step breaks before its result is built (EH-07-001)."""
    by_id = {entry.embargo_id: entry for entry in entries}
    triggers = {change.trigger for change in changes}
    violations: list[str] = []
    if any(entry.status == _S.TERMINATED for entry in entries):
        violations.append(
            "an entry is TERMINATED, so the register accepts no further"
            " change (invariant 4)"
        )
    duplicates = repeated_ids([change.embargo_id for change in changes])
    if duplicates:
        violations.append(f"one step changes {duplicates} more than once")
    for change in changes:
        entry = by_id.get(change.embargo_id)
        current = entry.status if entry is not None else None
        try:
            register_status_after(current, change.trigger)
        except VultronInvalidStateTransitionError as exc:
            violations.append(f"'{change.embargo_id}': {exc}")
    if _T.SUPERSEDE in triggers and _T.ACTIVATE not in triggers:
        violations.append(
            "SUPERSEDE is legal only in the step that activates another entry"
        )
    if _T.CANCEL in triggers and _T.TERMINATE not in triggers:
        active_before = any(entry.status == _S.ACTIVE for entry in entries)
        if not threat_signal or active_before:
            violations.append(
                "CANCEL is legal only with a TERMINATE, or on a threat"
                " signal while no entry is ACTIVE"
            )
    return violations


def _entry_after(
    entry: EmbargoRegisterEntry | None,
    change: RegisterChange,
    superseded_id: str | None,
) -> EmbargoRegisterEntry:
    status = register_status_after(
        entry.status if entry is not None else None, change.trigger
    )
    if entry is None:
        return EmbargoRegisterEntry(
            embargo=change.embargo or change.embargo_id, status=status
        )
    update: dict[str, object] = {"status": status}
    if change.trigger == _T.ACTIVATE and superseded_id is not None:
        update["replaces"] = superseded_id
    if change.termination is not None:
        update["termination"] = change.termination
    # Revalidate rather than ``model_copy``: the copy skips validators.
    return EmbargoRegisterEntry.model_validate(
        {**entry.model_dump(), **update, "embargo": entry.embargo}
    )


def apply_register_step(
    entries: Sequence[EmbargoRegisterEntry],
    changes: Sequence[RegisterChange],
    *,
    threat_signal: bool = False,
) -> list[EmbargoRegisterEntry]:
    """Return the register after one step of *changes*, or raise.

    The step's triggers are checked together (ADR-0122): each must be legal
    for its entry, ``SUPERSEDE`` needs an ``ACTIVATE`` in the same step,
    ``CANCEL`` needs a ``TERMINATE`` in the same step or, when
    *threat_signal* is set, no ``ACTIVE`` entry before it, and once an entry
    is ``TERMINATED`` no step changes anything (invariant 4), and the step
    names exactly one EM trigger.  The result must then keep invariants 1–3,
    and EM derived before and after must be one of that trigger's moves in
    the EM transition table (ADR-0130, EMB-18-006).  Every node — the
    CASE_MANAGER and each replica — applies a step only through this
    function, so all of them make the same checks.  An activated entry
    records the entry it superseded in ``replaces``.  New entries are
    appended; none is removed.

    Raises:
        VultronInvalidStateTransitionError: naming every rule the step breaks;
            *entries* is left as it was.
    """
    violations = _step_violations(
        entries, changes, threat_signal=threat_signal
    )
    em_trigger: EM_Trigger | None = None
    try:
        em_trigger = register_step_em_trigger(changes)
    except VultronInvalidStateTransitionError as exc:
        violations.append(str(exc))
    if em_trigger is not None and not violations:
        by_change = {change.embargo_id: change for change in changes}
        superseded_id = next(
            (c.embargo_id for c in changes if c.trigger == _T.SUPERSEDE), None
        )
        known = {entry.embargo_id for entry in entries}
        after = [
            (
                _entry_after(entry, by_change[entry.embargo_id], superseded_id)
                if entry.embargo_id in by_change
                else entry
            )
            for entry in entries
        ]
        after.extend(
            _entry_after(None, change, superseded_id)
            for change in changes
            if change.embargo_id not in known
        )
        violations = register_invariant_violations(e.status for e in after)
        if not violations:
            violations = em_move_violations(entries, after, em_trigger)
        if not violations:
            return after
    raise VultronInvalidStateTransitionError(
        "Embargo register refused the step "
        f"{[(c.trigger.name, c.embargo_id) for c in changes]}: "
        + "; ".join(violations)
    )


def register_step_is_legal(
    entries: Sequence[EmbargoRegisterEntry],
    changes: Sequence[RegisterChange],
    *,
    threat_signal: bool = False,
) -> bool:
    """True when :func:`apply_register_step` would accept *changes*.

    For a caller that must write something else before the step lands, and
    only if the step will (the rejecting owner's consent row is frozen once
    its entry is ``REJECTED``, ADR-0122).
    """
    try:
        apply_register_step(entries, changes, threat_signal=threat_signal)
    except VultronInvalidStateTransitionError:
        return False
    return True


def _ids_with(
    entries: Sequence[EmbargoRegisterEntry], status: EmbargoRegisterStatus
) -> list[str]:
    return [entry.embargo_id for entry in entries if entry.status == status]


def proposal_changes(embargo: str | EmbargoEvent) -> list[RegisterChange]:
    """The step that proposes *embargo*: one new ``PROPOSED`` entry."""
    embargo_id = _as_id(embargo)
    assert embargo_id is not None
    return [
        RegisterChange(
            embargo_id=embargo_id,
            trigger=_T.PROPOSE,
            embargo=embargo if isinstance(embargo, EmbargoEvent) else None,
        )
    ]


def activation_changes(
    entries: Sequence[EmbargoRegisterEntry], embargo_id: str
) -> list[RegisterChange]:
    """The step that activates *embargo_id*, superseding any ``ACTIVE`` entry."""
    return [
        RegisterChange(embargo_id=embargo_id, trigger=_T.ACTIVATE),
        *(
            RegisterChange(embargo_id=active_id, trigger=_T.SUPERSEDE)
            for active_id in _ids_with(entries, _S.ACTIVE)
        ),
    ]


def rejection_changes(embargo_id: str) -> list[RegisterChange]:
    """The step that rejects the proposal *embargo_id*."""
    return [RegisterChange(embargo_id=embargo_id, trigger=_T.REJECT)]


def termination_changes(
    entries: Sequence[EmbargoRegisterEntry], termination: EmbargoTermination
) -> list[RegisterChange]:
    """End the embargo in force with *termination*; cancel proposals (EP-08-004)."""
    return [
        *(
            RegisterChange(
                embargo_id=active_id,
                trigger=_T.TERMINATE,
                termination=termination,
            )
            for active_id in _ids_with(entries, _S.ACTIVE)
        ),
        *(
            RegisterChange(embargo_id=proposed_id, trigger=_T.CANCEL)
            for proposed_id in _ids_with(entries, _S.PROPOSED)
        ),
    ]


def carry_embargo_inline(
    entries: Sequence[EmbargoRegisterEntry], embargo: EmbargoEvent
) -> list[EmbargoRegisterEntry]:
    """*entries* with *embargo*'s entry holding the object, not its id.

    For a copy of a case about to be sent: a recipient cannot dereference an
    embargo it does not hold (AKM-03-001, EMB-18-003).  The status is
    unchanged, so this is not a register step.
    """
    return [
        (
            entry.model_copy(update={"embargo": embargo})
            if entry.embargo_id == embargo.id_
            else entry
        )
        for entry in entries
    ]


__all__ = [
    "EmbargoRegisterEntry",
    "carry_embargo_inline",
    "RegisterChange",
    "activation_changes",
    "apply_register_step",
    "em_move_violations",
    "proposal_changes",
    "register_step_em_trigger",
    "rejection_changes",
    "repeated_ids",
    "termination_changes",
]
