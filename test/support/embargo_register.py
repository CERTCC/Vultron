"""Build a case's embargo register in tests (ADR-0122).

A case's embargoes, and the EM state derived from them, live only in
``VulnerabilityCase.embargo_register``.  Tests that need a case in a given EM
state either drive the register through its steps (:func:`propose`,
:func:`activate`, :func:`reject`, :func:`terminate`, :func:`cancel_on_threat`)
— the same step builders ``EmbargoLifecycle`` applies — or build entries for
a constructor (:func:`register`).  Both go through the register's own rules,
so a fixture cannot hold a register no protocol event could have produced.
"""

from collections.abc import Iterable

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_register import (
    EmbargoRegisterEntry,
    RegisterChange,
    activation_changes,
    apply_register_step,
    proposal_changes,
    rejection_changes,
    termination_changes,
)
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    RegisterTrigger,
    TerminationReason,
)

EmbargoRef = str | EmbargoEvent


def _id(embargo: EmbargoRef) -> str:
    return embargo.id_ if isinstance(embargo, EmbargoEvent) else embargo


def propose(case: VulnerabilityCase, *embargoes: EmbargoRef) -> None:
    """Add each embargo to *case*'s register as an open proposal."""
    for embargo in embargoes:
        if case.embargo_register_entry(_id(embargo)) is None:
            case.apply_embargo_register_step(proposal_changes(embargo))


def activate(case: VulnerabilityCase, embargo: EmbargoRef) -> None:
    """Make *embargo* the embargo in force, proposing it first if needed."""
    propose(case, embargo)
    case.apply_embargo_register_step(
        activation_changes(case.embargo_register, _id(embargo))
    )


def reject(case: VulnerabilityCase, embargo: EmbargoRef) -> None:
    """The case owner's rejection of the open proposal *embargo*."""
    case.apply_embargo_register_step(rejection_changes(_id(embargo)))


def terminate(
    case: VulnerabilityCase,
    reason: TerminationReason = TerminationReason.EARLY,
) -> None:
    """End the embargo in force and cancel every open proposal."""
    case.apply_embargo_register_step(
        termination_changes(case.embargo_register, reason)
    )


def cancel_on_threat(case: VulnerabilityCase, *embargoes: EmbargoRef) -> None:
    """Cancel open proposals on a threat signal, with no embargo in force."""
    case.apply_embargo_register_step(
        [
            RegisterChange(embargo_id=_id(e), trigger=RegisterTrigger.CANCEL)
            for e in embargoes
        ],
        threat_signal=True,
    )


def register(
    *,
    active: EmbargoRef | None = None,
    proposed: Iterable[EmbargoRef] = (),
    terminated: EmbargoRef | None = None,
) -> list[EmbargoRegisterEntry]:
    """Register entries for a ``VulnerabilityCase(embargo_register=...)``.

    *active* is the embargo in force and each of *proposed* an open proposal;
    *terminated* is an embargo that has ended, which no other entry may
    accompany here (invariants 1 and 3).
    """
    proposed = list(proposed)
    if terminated is not None:
        if active is not None or proposed:
            raise ValueError("a terminated register holds no open entry")
        return [
            EmbargoRegisterEntry(
                embargo=terminated, status=EmbargoRegisterStatus.TERMINATED
            )
        ]
    entries: list[EmbargoRegisterEntry] = []
    if active is not None:
        entries.append(
            EmbargoRegisterEntry(
                embargo=active, status=EmbargoRegisterStatus.ACTIVE
            )
        )
    for embargo in proposed:
        entries = apply_register_step(entries, proposal_changes(embargo))
    return entries


__all__ = [
    "activate",
    "cancel_on_threat",
    "propose",
    "register",
    "reject",
    "terminate",
]
