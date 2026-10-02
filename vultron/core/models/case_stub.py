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
"""The core form of a case stub received on the wire (CM-11-003, CM-11-013).

A case stub (``VulnerabilityCaseStub``) is wire vocabulary with no domain
model of its own: an invitee never holds it as a record, and the CASE_MANAGER
holds the case it stands for.  What core needs from one is the case it names,
so the extractor promotes an inbound stub to :class:`CaseStubReference` at
the wire edge (ADR-0032), and every consumer resolves the case from
:attr:`CaseStubReference.case_id` — never from the stub's own ID.
"""

from vultron.core.models.base import CoreObject, NonEmptyString


class CaseStubReference(CoreObject):
    """A reference to a case stub, naming the case it stands for.

    ``id_`` and ``type_`` are the stub's own (``<case-id>/stub``,
    ``VulnerabilityCaseStub``); :attr:`case_id` is the case.  The class keeps
    ``type_`` abstract, so it registers in no type map: it is an in-process
    projection the extractor builds, like the bare :class:`CoreObject` it wraps
    an otherwise-unmodelled object in.  It is never stored as a record of its
    own: it travels only inline, inside the activity that carries it, and
    persistence keeps it inline there (``_KEEP_INLINE_NESTED_TYPES``).
    """

    case_id: NonEmptyString


def stub_case_id(obj: object) -> str | None:
    """The case *obj* names when it is a case stub, else ``None`` (CM-11-003).

    The one reader of a stub's case: a consumer that has a stub-Invite
    ``target`` (or the nested Invite's) calls this instead of reading the
    target's ID, which is the stub's own.
    """
    return obj.case_id if isinstance(obj, CaseStubReference) else None
