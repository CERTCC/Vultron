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
"""The CSAF adapter of the case projection port (ADR-0219)."""

import pytest

from test.support.case_projection import (
    COMMITTED_AT,
    PROJECTOR,
    projected_case,
    projected_ledger,
)
from vultron.adapters.driven.case_projection import CsafProjectionAdapter
from vultron.core.models.case_projection import (
    ProjectionCut,
    ProjectionInputs,
    PublicationStatus,
)
from vultron.core.models.case_projection_profile import (
    JOINED_PROFILE,
    PUBLIC_PROFILE,
    ProjectionProfile,
)
from vultron.core.ports.case_projection import CaseProjectionPort
from vultron.wire.csaf.projection import csaf_category, render_csaf


def test_the_adapter_is_a_projection_port() -> None:
    assert isinstance(CsafProjectionAdapter(), CaseProjectionPort)


@pytest.mark.spec("CSAF-06-004")
@pytest.mark.parametrize(
    "profile", [PUBLIC_PROFILE, JOINED_PROFILE], ids=lambda p: p.name
)
def test_the_adapter_renders_the_category_the_selection_gives(
    profile: ProjectionProfile,
) -> None:
    cut = ProjectionCut.of(projected_case(), projected_ledger(), profile)
    inputs = ProjectionInputs(
        status=PublicationStatus.INTERIM,
        projecting_actor=PROJECTOR,
        position_committed_at=COMMITTED_AT,
    )

    rendered = CsafProjectionAdapter().render(cut, inputs)

    assert rendered == render_csaf(
        cut, inputs, category=csaf_category(cut.preview)
    )
