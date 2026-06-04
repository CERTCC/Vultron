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

"""Domain representation of a vulnerability report."""

from typing import Literal

from pydantic import Field

from vultron.core.models.base import CoreObject


class VulnerabilityReport(CoreObject):
    """Domain representation of a vulnerability report.

    Canonical core type for the Vultron ``VulnerabilityReport`` object.
    ``type_`` is ``"VulnerabilityReport"`` to match the wire value and to
    auto-register this class in :data:`CORE_VOCABULARY`.

    Policy implementations receive this type when evaluating credibility
    and validity.  The wire-layer class in
    ``vultron.wire.as2.vocab.objects.vulnerability_report`` re-exports
    this type and adds AS2-specific serialization via :meth:`from_core`
    and :meth:`to_core`.
    """

    type_: Literal["VulnerabilityReport"] = Field(
        default="VulnerabilityReport",
        validation_alias="type",
        serialization_alias="type",
    )


#: Backward-compatibility alias; prefer :class:`VulnerabilityReport` in new code.
VultronReport = VulnerabilityReport


__all__ = ["VulnerabilityReport", "VultronReport"]
