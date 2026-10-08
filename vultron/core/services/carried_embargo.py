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
the announce seed, the create/engage replica stores, and the inbox pre-store
— calls :func:`store_carried_embargo` *first*.  It stores the
``EmbargoEvent`` the sender carried inline (``_case_for_wire``, AKM-03-001)
and refuses a bare reference the store lacks, rather than letting the case
land pointing at nothing.

Without the stored record a replica held a case pointing at an object it
could not read: the manager's teardown then failed to announce
(``terminate_embargo`` reads the ``EmbargoEvent`` first and raised), and every
participant kept an embargo already torn down, with EM stuck at ACTIVE.
"""

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.services.embargo_ordering import read_embargo_event
from vultron.errors import VultronValidationError


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
    anything is written: the inbox pre-store runs ahead of the handler's
    trust checks, and a first write wins, so a sender must not be able to
    plant another case's embargo under an id that case will later name.

    Raises:
        VultronNotFoundError: If the case names, by bare reference, an
            embargo *store* does not hold.
        VultronValidationError: If the named record is not an
            ``EmbargoEvent``, or an inline embargo belongs to another case.
    """
    # A received event's ``case`` property is a cast, so the object handed
    # in may be a bare reference stub with no case fields.
    if not isinstance(case_obj, VulnerabilityCase):
        return
    embargo_ref = case_obj.active_embargo
    if embargo_ref is None:
        return
    if isinstance(embargo_ref, EmbargoEvent):
        embargo_id = embargo_ref.id_
        if embargo_ref.context != case_obj.id_:
            raise VultronValidationError(
                f"Case '{case_obj.id_}' carries embargo '{embargo_id}' whose"
                f" context is '{embargo_ref.context}', not this case."
            )
        if store.read(embargo_id) is None:
            store.save(embargo_ref)
    else:
        embargo_id = str(embargo_ref)
    read_embargo_event(store, embargo_id)


__all__ = ["store_carried_embargo"]
