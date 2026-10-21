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


"""Hold a received case's active embargo before the case is saved (EMB-18-003).

A case that names an embargo its store cannot read breaks the invariant the
EP-05-001 comparison rests on, so every path that saves a received case —
the announce seed and the create/engage replica stores — calls
:func:`store_carried_embargo` *first*, as does the inbox's routing stage for
the throwaway store it rebuilds the activity in.  It stores the
``EmbargoEvent`` the sender carried inline (``_case_for_wire``, AKM-02-004)
and refuses a bare reference the store lacks, rather than letting the case
land pointing at nothing.

Without the stored record a replica held a case pointing at an object it
could not read: the manager's teardown then failed to announce
(``terminate_embargo`` reads the ``EmbargoEvent`` first and raised), and every
participant kept an embargo already torn down, with EM stuck at ACTIVE.

:func:`carried_entry_embargo` and :func:`entry_embargo` are the same rule for
a ledger entry that names an embargo, for the replica slots that apply it.
Every path checks the inline copy and the record already held under its id
alike (:func:`hold_embargo_for_case` for a case, EMB-18-004): its ``context``
must be the case or one of the case's reports (EP-04-009).
"""

from pydantic import ValidationError

from vultron.core.models._helpers import project_wire_snapshot_to_core
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.services.embargo_ordering import read_embargo_event
from vultron.errors import VultronNotFoundError, VultronValidationError


def store_carried_embargo(
    case_obj: VulnerabilityCase, store: CasePersistence | DataLayer
) -> None:
    """Make the embargo *case_obj* names readable in *store*, or raise.

    An inline ``EmbargoEvent`` is stored as its own record when *store* does
    not hold it yet; a bare reference must already resolve.  Either way the
    named embargo is read back through :func:`read_embargo_event`, so a
    caller that saves the case afterwards never writes a dangling
    ``active_embargo``.  A case with no active embargo needs nothing.

    An inline embargo whose ``context`` is not *case_obj* is refused before
    anything is written: a first write wins, so a sender must not be able to
    plant another case's embargo under an id that case will later name.  The
    record *store* already holds under the named id is checked the same way,
    whether the case carries the embargo inline or names it by bare id.  An
    embargo about one of *case_obj*'s reports counts as the case's: a
    Reporter's proposal names its report until the case exists (EP-04-009,
    EMB-18-004).

    Raises:
        VultronNotFoundError: If the case names, by bare reference, an
            embargo *store* does not hold.
        VultronValidationError: If the named record is not an
            ``EmbargoEvent``, or the inline embargo or the held record
            belongs to another case.
    """
    # A received event's ``case`` property is a cast, so the object handed
    # in may be a bare reference stub with no case fields.
    if not isinstance(case_obj, VulnerabilityCase):
        return
    embargo_ref = case_obj.active_embargo
    if embargo_ref is None:
        return
    hold_embargo_for_case(
        store,
        case_obj,
        embargo_ref
        if isinstance(embargo_ref, EmbargoEvent)
        else str(embargo_ref),
    )


def hold_embargo_for_case(
    store: CasePersistence | DataLayer,
    case: VulnerabilityCase,
    embargo: EmbargoEvent | str,
) -> EmbargoEvent:
    """Hold *embargo* in *store* as *case*'s, and return the held record.

    An inline ``EmbargoEvent`` is stored when *store* lacks it; a bare id
    must already resolve.  The inline copy and the held record must both be
    *case*'s, about *case* or one of its reports (EMB-18-004), and the inline
    copy is checked before anything is written.

    Raises:
        VultronNotFoundError: *embargo* is a bare id *store* does not hold.
        VultronValidationError: the inline copy or the held record belongs
            to another case, or the held record is not an ``EmbargoEvent``.
    """
    subjects = _case_subjects(case)
    if isinstance(embargo, EmbargoEvent):
        embargo_id = embargo.id_
        _require_this_case(subjects, case.id_, embargo_id, embargo.context)
        if store.read(embargo_id) is None:
            store.save(embargo)
    else:
        embargo_id = embargo
    return _held_embargo(store, subjects, case.id_, embargo_id)


def _held_embargo(
    store: CasePersistence | DataLayer,
    subjects: frozenset[str],
    case_id: str,
    embargo_id: str,
) -> EmbargoEvent:
    """The ``EmbargoEvent`` *store* holds under *embargo_id*, for the case.

    The record a case would name is the stored one, so its ``context`` is
    checked as an inline copy's is (EMB-18-004): it must be one of
    *subjects*, the case or a report it holds, since a Reporter's proposal
    names its report before the case exists and keeps its id once it is
    about the case (EP-04-004, EP-04-009).  Writes nothing.

    Raises:
        VultronNotFoundError: *store* holds no record under *embargo_id*.
        VultronValidationError: the held record is not an ``EmbargoEvent``,
            or its ``context`` is not one of *subjects*.
    """
    embargo = read_embargo_event(store, embargo_id)
    _require_this_case(subjects, case_id, embargo_id, embargo.context)
    return embargo


def _case_subjects(case: VulnerabilityCase) -> frozenset[str]:
    """The ``context`` values an embargo of *case* may carry (EP-04-009)."""
    reports = (
        r if isinstance(r, str) else r.id_ for r in case.vulnerability_reports
    )
    return frozenset((case.id_, *reports))


def _require_this_case(
    subjects: frozenset[str], case_id: str, embargo_id: str, context: object
) -> None:
    if context not in subjects:
        raise VultronValidationError(
            f"Case '{case_id}' names embargo '{embargo_id}' whose context is"
            f" '{context}', neither this case nor one of its reports."
        )


def _entry_subjects(
    store: CasePersistence | DataLayer, case_id: str
) -> frozenset[str]:
    """The ``context`` values a ledger entry's embargo may carry.

    The reports come from the replica's stored case.  A store that does not
    hold the case yet knows no report of it, so the entry's embargo must
    name the case itself.
    """
    case = store.read(case_id)
    if isinstance(case, VulnerabilityCase):
        return _case_subjects(case)
    return frozenset((case_id,))


def _entry_embargo_id(case_id: str, embargo_data: object) -> str:
    embargo_id = (
        embargo_data.get("id") or embargo_data.get("id_")
        if isinstance(embargo_data, dict)
        else embargo_data
    )
    if not isinstance(embargo_id, str) or not embargo_id:
        raise VultronValidationError(
            f"Ledger entry on case '{case_id}' names no embargo."
        )
    return embargo_id


def _inline_entry_embargo(
    subjects: frozenset[str],
    case_id: str,
    embargo_id: str,
    embargo_data: dict[str, object],
) -> EmbargoEvent:
    try:
        embargo = EmbargoEvent.model_validate(
            project_wire_snapshot_to_core(EmbargoEvent, embargo_data)
        )
    except ValidationError as exc:
        raise VultronValidationError(
            f"Embargo '{embargo_id}' in the entry is malformed: {exc}"
        ) from exc
    _require_this_case(subjects, case_id, embargo_id, embargo.context)
    return embargo


def entry_embargo(
    store: CasePersistence | DataLayer, case_id: str, embargo_data: object
) -> EmbargoEvent:
    """The ``EmbargoEvent`` a ledger entry carries, as the entry carries it.

    For a replica slot that copies the embargo into the register: an inline
    copy is the CASE_MANAGER's record, so it is returned as carried (never
    the copy *store* may already hold); a bare id names a record *store*
    must hold (EMB-18-003).  A record *store* holds under the id must be
    this case's, as the inline copy must: about the case or one of the
    reports the replica's stored case holds (EMB-18-004).  Writes nothing.

    Raises:
        VultronNotFoundError: the entry names, by bare reference, an embargo
            *store* does not hold.
        VultronValidationError: the entry names no embargo, the inline copy
            is malformed or belongs to another case, or the held record is
            not an ``EmbargoEvent`` or belongs to another case.
    """
    embargo_id = _entry_embargo_id(case_id, embargo_data)
    subjects = _entry_subjects(store, case_id)
    if not isinstance(embargo_data, dict):
        return _held_embargo(store, subjects, case_id, embargo_id)
    embargo = _inline_entry_embargo(
        subjects, case_id, embargo_id, embargo_data
    )
    if store.read(embargo_id) is not None:
        _held_embargo(store, subjects, case_id, embargo_id)
    return embargo


def carried_entry_embargo(
    store: CasePersistence | DataLayer, case_id: str, embargo_data: object
) -> EmbargoEvent | None:
    """The ``EmbargoEvent`` a ledger entry carries that *store* still lacks.

    For a replica slot that changes the register entry the entry names: the
    record must be held in the same store (EMB-18-003).  Returns ``None``
    when *store* already holds it, else the validated inline copy for the
    caller to store once the entry has applied, so a refused entry stores
    nothing.  An inline copy and a held record must both be this case's:
    about the case or one of the reports the replica's stored case holds
    (EMB-18-004).  The inline copy is checked even when the record is held,
    as :func:`entry_embargo` checks it.  Writes nothing.

    Raises:
        VultronNotFoundError: the entry names, by bare reference, an embargo
            *store* does not hold.
        VultronValidationError: the inline copy is malformed, or it or the
            held record belongs to another case, or the held record is not
            an ``EmbargoEvent``.
    """
    embargo_id = _entry_embargo_id(case_id, embargo_data)
    subjects = _entry_subjects(store, case_id)
    inline = (
        _inline_entry_embargo(subjects, case_id, embargo_id, embargo_data)
        if isinstance(embargo_data, dict)
        else None
    )
    if store.read(embargo_id) is not None:
        _held_embargo(store, subjects, case_id, embargo_id)
        return None
    if inline is None:
        raise VultronNotFoundError("EmbargoEvent", embargo_id)
    return inline


__all__ = [
    "carried_entry_embargo",
    "entry_embargo",
    "hold_embargo_for_case",
    "store_carried_embargo",
]
