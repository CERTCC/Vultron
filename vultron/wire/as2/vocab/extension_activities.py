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

"""Vultron extension activity types: verbs AS2 does not define (VM-03-005).

Each refines an AS2 core activity, declares it as ``_as2_core_supertype`` and
is annotated ``VocabNamespace.VULTRON``, so it is sent as the list ``[own
type, core type]`` and gets a ``vultron:`` term in the JSON-LD context.  They
are public verb classes, like the AS2 base classes, not the factory layer's
internal shapes in :mod:`vultron.wire.as2.vocab.activities` (AF-05-001).
"""

from typing import ClassVar, Literal

from pydantic import Field

from vultron.wire.as2.enums import as_TransitiveActivityType as TA_type
from vultron.wire.as2.vocab.base.enums import VocabNamespace
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Reject


class as_Refuse(as_Reject):
    """The actor refuses the object: it will not admit the act.

    A Vultron extension type, ``vultron:Refuse``, a subtype of ``as:Reject``
    (ADR-0196).  A ``Reject`` is the actor's own decision against a request,
    such as a participant's decline of an ``Invite``; a ``Refuse`` is the
    CASE_MANAGER's refusal of an act a precondition did not admit
    (CLP-02-016, CLP-02-005).  It is sent as ``"type": ["Refuse", "Reject"]``,
    so a plain AS2 receiver still reads a ``Reject``, and a received list is
    read back as a ``Refuse``.  Once resolved it matches no ``Reject``
    pattern.
    """

    _vocab_ns: ClassVar[VocabNamespace] = VocabNamespace.VULTRON
    _as2_core_supertype = as_Reject

    type_: Literal[TA_type.REFUSE] = Field(  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]
        default=TA_type.REFUSE,
        validation_alias="type",
        serialization_alias="type",
    )
