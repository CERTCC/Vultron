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

from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.core.services.embargo_ordering import read_embargo_event


def store_carried_embargo(
    case_obj: object, store: CasePersistence | DataLayer
) -> None:
    """Make the embargo *case_obj* names readable in *store*, or raise.

    An inline ``EmbargoEvent`` is stored as its own record when *store* does
    not hold it yet; a bare reference must already resolve.  Either way the
    named embargo is read back through :func:`read_embargo_event`, so a
    caller that saves the case afterwards never writes a dangling
    ``active_embargo``.  A case with no active embargo needs nothing.

    Raises:
        VultronNotFoundError: If the case names, by bare reference, an
            embargo *store* does not hold.
        VultronValidationError: If the named record is not an
            ``EmbargoEvent``.
    """
    embargo_ref = getattr(case_obj, "active_embargo", None)
    if embargo_ref is None:
        return
    if isinstance(embargo_ref, EmbargoEvent):
        embargo_id = embargo_ref.id_
        if store.read(embargo_id) is None:
            store.save(embargo_ref)
    else:
        embargo_id = str(embargo_ref)
    read_embargo_event(store, embargo_id)


__all__ = ["store_carried_embargo"]
