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

"""Domain representation of a document attached to another object."""

from typing import Literal

from pydantic import Field

from vultron.core.models.base import CoreObject


class AttachedDocument(CoreObject):
    """A document carried in another object's ``attachment`` list.

    The canonical core type for an AS2 ``Document``: a sender attaches a CSAF
    document to a ``VulnerabilityReport`` as one, with the document's JSON
    text as its ``content`` and ``application/json`` as its ``media_type``
    (CSAF-01-001, CSAF-01-002).  The class is the wire form too (ARCH-25-003,
    ADR-0099), so a received report's attachments are core objects and keep
    their fields through ``dl.save`` and ``dl.read``.

    The document is kept exactly as it was received (VM-08-002).  What a
    receiver read from it lives in a record of its own, never on the
    document (CSAF-04-004).
    """

    type_: Literal["Document"] = Field(
        default="Document",
        validation_alias="type",
        serialization_alias="type",
    )


__all__ = ["AttachedDocument"]
