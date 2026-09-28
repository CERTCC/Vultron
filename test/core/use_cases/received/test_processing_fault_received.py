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
"""Tests for CreateProcessingFaultReceivedUseCase (ADR-0080, #2255)."""

from unittest.mock import MagicMock

import pytest

from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.fault import (
    CreateProcessingFaultReceivedUseCase,
)


@pytest.mark.spec("HP-01-003")
def test_received_fault_is_skipped_until_ask_register_exists():
    """Nothing correlates a NACK to its ask yet (#2883), so it is a no-op."""
    request = MagicMock()

    result = CreateProcessingFaultReceivedUseCase(
        MagicMock(), request
    ).execute()

    assert result.disposition == HandlerDisposition.SKIPPED
    assert result.reason is not None and "#2883" in result.reason
