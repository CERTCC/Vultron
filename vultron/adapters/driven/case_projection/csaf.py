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

"""The CSAF adapter of the case projection port (ADR-0219).

Renders a cut case as a CSAF 2.1 document through
:func:`~vultron.wire.csaf.projection.render_csaf`.  The category is the one
:func:`~vultron.wire.csaf.projection.csaf_category` selects for the cut's
preview, so every call site that renders CSAF takes it from that one
function (``csaf_base`` while the case holds no products, CSAF-06-004).

See also:
    - ``vultron/core/ports/case_projection.py`` — port Protocol
    - ``notes/csaf-projection.md`` § "Where the Code Goes"
"""

from pydantic import JsonValue

from vultron.core.models.case_projection import (
    ProjectionCut,
    ProjectionInputs,
)
from vultron.wire.csaf.projection import csaf_category, render_csaf


class CsafProjectionAdapter:
    """Render a cut case as a CSAF 2.1 document (CSAF-06)."""

    def render(
        self, cut: ProjectionCut, inputs: ProjectionInputs
    ) -> dict[str, JsonValue]:
        """Render *cut* with *inputs*, of the category its preview takes.

        Raises:
            VultronValidationError: When the preview shows no ledger
                position, or the projecting actor's id has no origin.
        """
        return render_csaf(cut, inputs, category=csaf_category(cut.preview))


__all__ = ["CsafProjectionAdapter"]
