#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Read helpers behind the datalayer router: stored offers, stored objects,
and the actor class a stored payload names.
"""

import json
from typing import Any, cast

from vultron.adapters.driving.fastapi.responses import AS2JSONResponse
from vultron.adapters.received_archive import (
    read_held_as_received,
    read_received_as_received,
)
from vultron.adapters.utils import full_object_id
from vultron.core.models.actor import CoreActor
from vultron.core.models.base import CoreObject
from vultron.core.models.protocols import PersistableModel
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vultron_actor import (
    as_VultronApplication,
    as_VultronGroup,
    as_VultronOrganization,
    as_VultronPerson,
    as_VultronService,
)

_OFFER_TYPE = "Offer"


def _read_offer(datalayer: DataLayer, offer_id: str) -> as_Offer | None:
    """The Offer *offer_id* as this actor holds it, or ``None``.

    Read as :func:`~vultron.adapters.received_archive.read_held_as_received`
    reads any activity this actor holds: a received one parsed from the body
    its archive record keeps, under a key the receiver derives from the
    sender's id (CLP-10-036, ADR-0149), since a receiver holds no received
    activity under the sender's id (DL-06-006); otherwise the row under
    *offer_id*, where an Offer the actor authored is stored.  *offer_id* may
    be a bare UUID, which names its ``urn:uuid:`` id: the store keys only on
    full ids (OID-02-004), so this helper maps it.

    Whatever is held under the id must be an Offer: every Offer a store holds
    is an ``as_Offer``, read back as its own class (ADR-0034) or parsed from
    its archived body, and ``as_Invite`` subclasses ``as_Offer`` but types
    itself ``Invite``, so a received Invite is not served as one.
    """
    try:
        held = read_held_as_received(
            cast(CasePersistence, datalayer),
            full_object_id(offer_id),
            _OFFER_TYPE,
        )
    except VultronNotFoundError:
        return None
    if not isinstance(held, as_Offer) or held.type_ != _OFFER_TYPE:
        return None
    return held


def _received_offers(datalayer: DataLayer) -> dict[str, as_Activity]:
    """Every Offer this actor received, keyed by the sender's id for it.

    Each is parsed from the body its archive record keeps, through the seam
    that reads a held body (:func:`read_received_as_received`), so the list
    and the single-Offer reads answer one received Offer the same way
    (CLP-10-017, ADR-0149).  The record is listed before it is read, so the
    read cannot miss.
    """
    return {
        record.activity_id: read_received_as_received(
            cast(CasePersistence, datalayer), record.activity_id, _OFFER_TYPE
        )
        for record in datalayer.list_objects(ReceivedActivityRecord.__name__)
        if isinstance(record, ReceivedActivityRecord)
        # Archived only: a body still held for a replay has not been
        # received into this actor's records yet (ADR-0154), and the
        # delivery that routes it may still refuse it.
        and record.stage is ReceivedStage.ARCHIVED
        and json.loads(record.received_body).get("type") == _OFFER_TYPE
    }


def _serve_stored(obj: PersistableModel) -> AS2JSONResponse | dict[str, Any]:
    """Serve *obj* as the store holds it, without rebuilding it.

    ``dl.read()`` already returns the typed object (ADR-0034), and a
    ``CoreObject`` is its own AS2 class (ADR-0099), so it renders as AS2
    directly.  Rebuilding it from its dump ran its construction validators
    again, and a validator that seeds a default drew an id and read the
    clock: a read then shifted every id a seeded demo run minted after it
    (#5510).  A bookkeeping row that has no AS2 form is served as its plain
    dump.
    """
    if isinstance(obj, (as_Base, CoreObject)):
        return AS2JSONResponse(obj)
    # JSON mode, so a bookkeeping row's own serializers run and every time it
    # carries is answered in the fixed form (CS-13-007).
    return obj.model_dump(mode="json", by_alias=True, serialize_as_any=True)


_DATALAYER_ACTOR_TYPE_MAP: dict[str, type[as_Actor | CoreActor]] = {
    "Person": as_VultronPerson,
    "Organization": as_VultronOrganization,
    "Service": as_VultronService,
    "Application": as_VultronApplication,
    "Group": as_VultronGroup,
}


def _actor_class_for_payload(
    payload: dict[str, Any],
) -> type[as_Actor | CoreActor]:
    payload_type = payload.get("type_") or payload.get("type")
    if isinstance(payload_type, str):
        return _DATALAYER_ACTOR_TYPE_MAP.get(payload_type, as_Actor)
    return as_Actor
