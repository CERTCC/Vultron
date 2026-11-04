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


"""Check and apply one register step against the register invariants.

Each step names one EM trigger, and the EM derived before and after it must
be one of that trigger's moves (ADR-0122, ADR-0130).
"""

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from vultron.core.models.embargo_register.entry import (
    _S,
    _T,
    EmbargoRegisterEntry,
    RegisterChange,
    repeated_ids,
)
from vultron.core.states.em import EM_Trigger, is_em_transition
from vultron.core.states.embargo_register import (
    RegisterTrigger,
    derive_em,
    register_invariant_violations,
    register_status_after,
)
from vultron.errors import VultronInvalidStateTransitionError

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

    Both registers must pass :func:`register_invariant_violations`, so EM
    derives from each (ADR-0122); the move must then be in the EM transition
    table (ADR-0130, EMB-18-006).  An empty list means the move is legal.
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
    is ``TERMINATED`` no step changes anything, and the step names exactly
    one EM trigger.  The result must then pass
    :func:`register_invariant_violations`, and EM derived before and after
    must be one of that trigger's moves in the EM transition table
    (ADR-0130, EMB-18-006).  Every node — the CASE_MANAGER and each replica —
    applies a step only through this function, so all of them make the same
    checks.  An activated entry
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
