"""Build a case's embargo register in tests (ADR-0122).

A case's embargoes, and the EM state derived from them, live only in
``VulnerabilityCase.embargo_register``.  Tests that need a case in a given EM
state either drive the register through its steps (:func:`propose`,
:func:`activate`, :func:`reject`, :func:`terminate`, :func:`cancel_on_threat`)
— the same step builders ``EmbargoLifecycle`` applies — or build entries for
a constructor (:func:`register`).  Both go through the register's own rules,
so a fixture cannot hold a register no protocol event could have produced.

The register holds each embargo whole, with its own status (ADR-0202).  A
helper given an embargo id alone registers a stand-in ``EmbargoEvent`` under
that id (:func:`stand_in`), for a test that needs only the id; a test whose
code under test reads the embargo's terms passes the ``EmbargoEvent``.
"""

from collections.abc import Iterable
from datetime import UTC, datetime

from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_register import (
    RegisterChange,
    activation_changes,
    apply_register_step,
    proposal_changes,
    rejection_changes,
    termination_changes,
)
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    RegisterTrigger,
)
from vultron.core.states.participant_embargo_consent import PEC_Trigger

EmbargoRef = str | EmbargoEvent

#: The terms a stand-in embargo carries: published long ago, ending far ahead.
STAND_IN_PUBLISHED = datetime(2026, 1, 1, tzinfo=UTC)
STAND_IN_END_TIME = datetime(2099, 1, 1, tzinfo=UTC)
_STAND_IN_CONTEXT = "urn:uuid:stand-in-case"


def _id(embargo: EmbargoRef) -> str:
    return embargo.id_ if isinstance(embargo, EmbargoEvent) else embargo


def stand_in(embargo: EmbargoRef, context: str | None = None) -> EmbargoEvent:
    """*embargo* itself, or a stand-in ``EmbargoEvent`` under the id it is.

    The stand-in's terms are :data:`STAND_IN_PUBLISHED` and
    :data:`STAND_IN_END_TIME`, its context *context* (else a fixed one).
    """
    if isinstance(embargo, EmbargoEvent):
        return embargo
    return EmbargoEvent(
        id_=embargo,
        context=context or _STAND_IN_CONTEXT,
        published=STAND_IN_PUBLISHED,
        updated=None,
        start_time=None,
        end_time=STAND_IN_END_TIME,
    )


def propose(case: VulnerabilityCase, *embargoes: EmbargoRef) -> None:
    """Add each embargo to *case*'s register as an open proposal."""
    for embargo in embargoes:
        if case.registered_embargo(_id(embargo)) is None:
            case.apply_embargo_register_step(
                proposal_changes(stand_in(embargo, case.id_))
            )


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
    termination: EmbargoTermination | None = None,
) -> None:
    """End the embargo in force and cancel every open proposal.

    *termination* defaults to an early end for an ``OTHER`` cause.
    """
    case.apply_embargo_register_step(
        termination_changes(
            case.embargo_register, termination or EmbargoTermination.other()
        )
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
) -> list[EmbargoEvent]:
    """A register for a ``VulnerabilityCase(embargo_register=...)``.

    *active* is the embargo in force and each of *proposed* an open proposal;
    *terminated* is an embargo that has ended, which no other entry may
    accompany here (invariants 1 and 3).
    """
    proposed = list(proposed)
    if terminated is not None:
        if active is not None or proposed:
            raise ValueError("a terminated register holds no open entry")
        return [
            registered(terminated, status=EmbargoRegisterStatus.TERMINATED)
        ]
    entries: list[EmbargoEvent] = []
    if active is not None:
        entries.append(registered(active, status=EmbargoRegisterStatus.ACTIVE))
    for embargo in proposed:
        entries = apply_register_step(
            entries, proposal_changes(stand_in(embargo))
        )
    return entries


def registered(
    embargo: EmbargoRef,
    *,
    status: EmbargoRegisterStatus,
    replaces: str | None = None,
    termination: EmbargoTermination | None = None,
) -> EmbargoEvent:
    """*embargo* (or its :func:`stand_in`) holding the register state given.

    For a register built whole, which no step produced; a ``TERMINATED``
    embargo given no *termination* ends for an ``OTHER`` cause.  Validated,
    so a state no embargo may hold is refused (ADR-0202).
    """
    if status == EmbargoRegisterStatus.TERMINATED and termination is None:
        termination = EmbargoTermination.other()
    return EmbargoEvent.model_validate(
        {
            **stand_in(embargo).model_dump(),
            "status": status,
            "replaces": replaces,
            "termination": termination,
        }
    )


def write_consent_rows(dl: CasePersistence, case: VulnerabilityCase) -> None:
    """Write each participant's ``UNINVITED`` row for every register entry.

    The rows a proposal and a join write in production (ADR-0122), for a
    fixture that built *case*'s register with the helpers above, which touch
    only the case.  Reads every participant record *case* lists from *dl* and
    saves the ones that gained a row; rows already held are kept.
    """
    embargo_ids = case.register_embargo_ids
    for entry in case.case_participants:
        participant_id = _as_id(entry)
        record = dl.read(participant_id) if participant_id else None
        if isinstance(record, CaseParticipant) and (
            record.write_uninvited_rows(embargo_ids)
        ):
            dl.save(record)


def agree_to_active_embargo(
    dl: CasePersistence, case: VulnerabilityCase, *actor_ids: str
) -> None:
    """Make each of *actor_ids* a signatory to *case*'s active embargo.

    Its row for the embargo in force moves to ``AGREED`` through the one
    consent-write path (``apply_pec_transition``, CM-18-005), so the actor is
    an active participant (CM-10-004).  For a fixture whose sender must be
    entitled to act on an embargoed case (CM-23-018).  Call it after
    :func:`write_consent_rows`, which gives each participant its rows.  An
    actor that already agreed is left as it is.

    Raises:
        AssertionError: *case* has no embargo in force, or an actor is not
            on its roster.
    """
    embargo_id = case.active_embargo_id
    assert embargo_id is not None, f"case '{case.id_}' has no active embargo"
    for actor_id in actor_ids:
        participant_id = case.actor_participant_index.get(actor_id)
        assert participant_id is not None, f"'{actor_id}' is not on the roster"
        record = dl.read(participant_id)
        assert isinstance(record, CaseParticipant), participant_id
        if record.is_signatory(embargo_id):
            continue
        record.apply_pec_transition(
            embargo_id,
            PEC_Trigger.AGREE,
            entry_status=EmbargoRegisterStatus.ACTIVE,
        )
        dl.save(record)


__all__ = [
    "activate",
    "agree_to_active_embargo",
    "cancel_on_threat",
    "propose",
    "register",
    "registered",
    "reject",
    "stand_in",
    "terminate",
    "write_consent_rows",
]
