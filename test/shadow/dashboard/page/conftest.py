"""The page tests' fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from streamlit.testing.v1 import AppTest

from test.shadow.dashboard._support import TIMEOUT
from vultron.config import config_override
from vultron.demo.recordings.layout import RECORDINGS_DIR
from vultron.shadow.dashboard.app import APP_PATH


@pytest.fixture
def recordings_app() -> Iterator[AppTest]:
    """The page over the committed recordings, not yet run."""
    with config_override(VULTRON_SHADOW__LEDGER_DIR=str(RECORDINGS_DIR)):
        yield AppTest.from_file(str(APP_PATH), default_timeout=TIMEOUT)
