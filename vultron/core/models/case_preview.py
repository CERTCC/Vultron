#!/usr/bin/env python

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
"""The core form of the case preview a stub Invite carries (ADR-0205).

The stub Invite's ``object`` is a typed reference to the case carrying the
case's preview, the case stub (CM-17-010).  A preview is not the case
(MV-10-013): an invitee never holds it as a record, and no replica is seeded
from it.  The extractor carries it into core at the wire edge (ADR-0032) as a
:class:`PreviewedCaseReference`, which names the case by its own ``id`` and
holds the preview's content as a :class:`CasePreview`, so a consumer reads
the case from the reference's ``id`` and what the invitee decides on from
the preview.
"""

from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.states.em import EM


class CasePreview(CoreObject):
    """What a case's preview shows an invitee (CM-17-010, CM-17-002).

    ``summary`` is the human-readable context the sender chose (MV-10-001).
    With an embargo in force, ``active_embargo`` is its terms, the whole
    ``EmbargoEvent`` or its id as the preview carried it (CM-17-011), and
    ``em_state`` the case's EM state (CM-17-013).  ``id_`` and ``type_``
    are the preview's own, which no reader derives the case from.

    The class declares no ``Literal`` ``type_``, so ``CORE_TYPE_MAP`` keys it
    on its class name, which no wire or stored ``type`` carries.  It is an
    in-process projection the extractor builds, never stored as a record.
    """

    summary: NonEmptyString
    active_embargo: EmbargoEvent | NonEmptyString | None = None
    em_state: EM | None = None


class PreviewedCaseReference(CoreObject):
    """A case named by typed reference, carrying the case's preview.

    ``id_`` is the case's id and ``type_`` its type, ``VulnerabilityCase``
    (ADR-0205).  :attr:`preview` is what the invitee may see before it
    joins.  The class declares no ``Literal`` ``type_``, so ``CORE_TYPE_MAP``
    keys it on its class name, ``PreviewedCaseReference``, which no wire or
    stored ``type`` carries.  It is an in-process projection the extractor
    builds, like the bare :class:`CoreObject` it wraps an otherwise
    unmodelled object in, and is never a case: no replica is built from it
    (MV-10-013).
    """

    preview: CasePreview  # type: ignore[assignment]


def case_preview_of(obj: object) -> CasePreview | None:
    """The preview *obj* carries when it is a previewed case reference."""
    return obj.preview if isinstance(obj, PreviewedCaseReference) else None


def previewed_case_id(obj: object) -> str | None:
    """The case *obj* names when it is a case reference carrying a preview.

    The one reader of a stub Invite's case from a recorded Invite's
    ``object``, as the store reads it back: the reference names the case by
    its own ``id`` (ADR-0205).  ``None`` for anything that carries no
    preview object, such as a whole case or an ``EmbargoEvent``.  AS2 lets
    any object's ``preview`` be a URI string; only an inline preview object
    is a case's preview (MV-10-012).
    """
    preview = getattr(obj, "preview", None)
    if preview is None or isinstance(preview, str):
        return None
    case_id = getattr(obj, "id_", None)
    return case_id if isinstance(case_id, str) and case_id else None
