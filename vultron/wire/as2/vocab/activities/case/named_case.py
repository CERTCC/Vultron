#!/usr/bin/env python
# pyright: reportGeneralTypeIssues=false
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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
"""The typed case reference a participant's act on a case names."""

from typing import Annotated

from pydantic import AfterValidator

from vultron.wire.as2.typed_reference import (
    as_TypedReference,
    is_case_reference,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


def _names_a_case(reference: as_TypedReference) -> as_TypedReference:
    """Refuse a typed reference that names an object other than a case."""
    if not is_case_reference(reference):
        raise ValueError(
            f"a typed reference of type {reference.type_!r} names no case;"
            " the object of an act on a case is the case (ADR-0165)"
        )
    return reference


#: The case a participant's act on it names: its typed reference, which every
#: factory builds (AKM-03-003, ADR-0165).  The reference is the generic typed
#: reference (ADR-0198) and must name a ``VulnerabilityCase``.  A full case
#: another sender still carries is accepted, and its receiver reads only its
#: id.
NamedCase = (
    Annotated[as_TypedReference, AfterValidator(_names_a_case)]
    | as_VulnerabilityCase
)
