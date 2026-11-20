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

"""Driven port for rendering a case projection as a document (ADR-0219).

A projection is made in two steps: the call site's profile cuts the case
and its ledger into a
:class:`~vultron.core.models.case_projection.ProjectionCut`, then a renderer
translates the cut, with the call site's
:class:`~vultron.core.models.case_projection.ProjectionInputs`, into a
document.  Core makes the cut (:mod:`vultron.core.services.case_projection`)
and reaches the renderer only through this port, because the renderer is
wire code core may not import (ARCH-01-001).

The port names no format.  Each format is an adapter: CSAF is the first
(``vultron/adapters/driven/case_projection/csaf.py``), and a CVE record or a
CERT Vulnerability Note is a later adapter behind the same port.  An adapter
decides what only its format knows, such as the CSAF category, from the cut
it is given.

A missing port is a wiring error, never a fallback
(:func:`~vultron.core.services.case_projection.require_projection_port`).

See also ``notes/csaf-projection.md`` § "Where the Code Goes".
"""

from typing import Protocol, runtime_checkable

from pydantic import JsonValue

from vultron.core.models.case_projection import (
    ProjectionCut,
    ProjectionInputs,
)


@runtime_checkable
class CaseProjectionPort(Protocol):
    """Render a cut case, with its call site's inputs, as one document."""

    def render(
        self, cut: ProjectionCut, inputs: ProjectionInputs
    ) -> dict[str, JsonValue]:
        """Render *cut* with *inputs* as a document of the adapter's format.

        The adapter reads only *cut* and *inputs*, never the case or its
        ledger, so it cannot show what the profile withheld (CSAF-06-001).

        Returns:
            The document, as JSON.

        Raises:
            VultronValidationError: When the cut cannot give a document,
                such as a preview that shows no ledger position.
        """
        ...


__all__ = ["CaseProjectionPort"]
