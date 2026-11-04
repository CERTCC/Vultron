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

"""The Vultron JSON-LD ``@context`` and the Vultron-property field marker."""

from pydantic.config import JsonDict

#: The Vultron JSON-LD ``@context``.  VM-10-001 (MUST) requires it on every
#: Vultron-specific object on the wire; the ActivityStreams namespace alone "is
#: not sufficient" for types AS2 does not define.
#:
#: It lives in core rather than beside ``ACTIVITY_STREAMS_NS`` in the wire layer
#: because under ADR-0099 the core classes *are* the objects that carry it, and
#: core MUST NOT import wire (ARCH-01-001 — the one boundary rule ADR-0099 leaves
#: fully in force).  Wire imports it from here, which ARCH-25-006 permits.
VULTRON_CONTEXT_URI = "https://certcc.github.io/Vultron/ns/context.jsonld"

#: Key of the ``json_schema_extra`` marker that declares a wire field a
#: Vultron-namespace property, such as a termination ``Remove``'s
#: ``terminationCause`` (EMB-13-005) or a case's ``ledgerPosition``
#: (SYNC-16-005).  The context generator maps each marked field's wire name to
#: ``vultron:<name>``, so a receiver can resolve it.  In core for the reason
#: :data:`VULTRON_CONTEXT_URI` is: core classes carry it (ADR-0099).
VULTRON_PROPERTY_KEY = "vultron_property"

#: The marker itself: pass it as a field's ``json_schema_extra``.
VULTRON_PROPERTY_EXTRA: JsonDict = {VULTRON_PROPERTY_KEY: True}
