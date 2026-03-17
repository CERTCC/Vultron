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

"""Tests for the UseCase protocol and UnknownUseCase reference implementation."""

from unittest.mock import MagicMock

import pytest

from vultron.core.models.events.unknown import UnknownReceivedEvent
from vultron.core.ports.use_case import UseCase
from vultron.core.use_cases.unknown import UnknownUseCase


@pytest.fixture
def mock_dl():
    return MagicMock()


@pytest.fixture
def unknown_event():
    return UnknownReceivedEvent(
        activity_id="https://example.org/activities/test-unknown",
        actor_id="https://example.org/actors/test-actor",
    )


class TestUseCaseProtocol:
    def test_protocol_is_non_generic(self):
        from typing import get_args

        # The new UseCase is non-generic: no type parameters
        assert get_args(UseCase) == ()

    def test_unknown_use_case_satisfies_protocol(self, mock_dl, unknown_event):
        use_case = UnknownUseCase(mock_dl, unknown_event)
        assert hasattr(use_case, "execute")
        assert callable(use_case.execute)

    def test_protocol_structural_check(self, mock_dl, unknown_event):
        use_case: UseCase = UnknownUseCase(mock_dl, unknown_event)
        assert use_case is not None


class TestUnknownUseCase:
    def test_execute_logs_warning(self, mock_dl, unknown_event, caplog):
        import logging

        use_case = UnknownUseCase(mock_dl, unknown_event)
        with caplog.at_level(logging.WARNING):
            use_case.execute()
        assert any("unknown use case" in r.message for r in caplog.records)

    def test_execute_does_not_raise(self, mock_dl, unknown_event):
        use_case = UnknownUseCase(mock_dl, unknown_event)
        result = use_case.execute()
        assert result is None

    def test_dl_injected_via_constructor(self, mock_dl, unknown_event):
        use_case = UnknownUseCase(mock_dl, unknown_event)
        assert use_case._dl is mock_dl

    def test_request_injected_via_constructor(self, mock_dl, unknown_event):
        use_case = UnknownUseCase(mock_dl, unknown_event)
        assert use_case._request is unknown_event
