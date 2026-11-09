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

"""Register the core :class:`AttachedDocument` as the wire ``Document``.

A report's attachments are core documents (CSAF-01-001), so the parser must
build one for an inline ``{"type": "Document"}`` rather than the bare AS2
``as_Document``, which the report's typed ``attachment`` list would refuse.
``as_Document`` stays as the base of the other AS2 document types
(``Image``, ``Page``, …), each of which keeps its own ``type`` value.
"""

from vultron.core.models.attached_document import AttachedDocument
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP

# Register core class in WIRE_TYPE_MAP so the parser admits it inline
# (ARCH-25-003, ADR-0099).
WIRE_TYPE_MAP["Document"] = AttachedDocument

__all__ = ["AttachedDocument"]
