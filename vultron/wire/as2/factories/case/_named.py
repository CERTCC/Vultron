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
"""The typed case reference a participant's act on a case names it by."""

from vultron.wire.as2.factories._context import (
    case_uri_of,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    as_VulnerabilityCaseReference,
    case_reference,
)


def _named_case(
    case: as_VulnerabilityCase | str,
) -> as_VulnerabilityCaseReference:
    """The typed reference a participant's act on *case* names it by.

    ``Join``, ``Ignore`` and ``Leave`` of a case and the ownership-transfer
    ``Offer`` name the case rather than carry a copy of it (AKM-03-003,
    ADR-0165): every receiver holds the case, so only its id travels, with
    the ``type`` a receiver routes by.  *case* may be the case the sender
    holds or its URI; nothing but the id is read from it.

    Raises:
        ValidationError: When *case* names no case id, which each factory
            reports as :exc:`VultronActivityConstructionError`.
    """
    return case_reference(case_uri_of(case) or "")
