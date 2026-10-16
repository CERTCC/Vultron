#!/usr/bin/env python

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

"""Tests for as_CaseParticipantRole role parsing (ADR-0039, ADR-0078)."""

import pytest
from pydantic import ValidationError

from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant_role import (
    as_CaseParticipantRole,
)


@pytest.mark.parametrize("raw", ["vendor", "VENDOR", CVDRole.VENDOR])
def test_role_parses_live_values(raw):
    """A live role parses whatever its case, or as the enum member."""
    role = as_CaseParticipantRole.model_validate({"role": raw}).role
    assert role is CVDRole.VENDOR


def test_offering_the_retired_finder_role_is_refused_with_its_reason():
    """An inbound offer of 'finder' is refused and names ADR-0078."""
    with pytest.raises(ValidationError, match="ADR-0078"):
        as_CaseParticipantRole.model_validate({"role": "finder"})
