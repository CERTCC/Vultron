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

"""``discover_actors()`` logs only the actor ID at INFO (SL-04-007).

The full ``logfmt()`` object dump is DEBUG-only: at INFO the only part of a
discovered actor that carries narrative value is its ID.
"""

import logging
from typing import cast

import pytest

from vultron.demo.utils import DataLayerClient, discover_actors

_UTILS_LOGGER = "vultron.demo.utils"

_FINDER_ID = "https://example.org/actors/finn"
_VENDOR_ID = "https://example.org/actors/vendorco"
_COORDINATOR_ID = "https://example.org/actors/cert"

_ACTORS: list[dict] = [
    {"type": "Person", "id": _FINDER_ID, "name": "Finn the Finder"},
    {"type": "Organization", "id": _VENDOR_ID, "name": "VendorCo Inc"},
    {"type": "Organization", "id": _COORDINATOR_ID, "name": "Coordinator CC"},
]


class _StubClient:
    """Minimal DataLayerClient stand-in returning a fixed actor list."""

    def get(self, path: str, **kwargs) -> list[dict]:
        assert path == "/actors/"
        return _ACTORS


@pytest.fixture()
def client() -> DataLayerClient:
    return cast(DataLayerClient, _StubClient())


def _found_records(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if "actor:" in r.getMessage()]


def test_info_records_contain_only_the_actor_id(client, caplog):
    """At INFO each discovered actor is reported by ID, not full object."""
    with caplog.at_level(logging.INFO, logger=_UTILS_LOGGER):
        finder, vendor, coordinator = discover_actors(client)

    assert finder.id_ == _FINDER_ID
    assert vendor.id_ == _VENDOR_ID
    assert coordinator.id_ == _COORDINATOR_ID

    info_records = [
        r for r in _found_records(caplog) if r.levelno == logging.INFO
    ]
    assert len(info_records) == 3, "Expected one INFO line per actor"
    messages = [r.getMessage() for r in info_records]
    assert messages == [
        f"Found finder actor: {_FINDER_ID}",
        f"Found vendor actor: {_VENDOR_ID}",
        f"Found coordinator actor: {_COORDINATOR_ID}",
    ]
    # The logfmt() dump renders the actor name; it must not appear at INFO.
    assert not any("Finn the Finder" in m for m in messages)


def test_full_object_dump_is_available_at_debug(client, caplog):
    """The full ``logfmt()`` dump is still emitted, at DEBUG."""
    with caplog.at_level(logging.DEBUG, logger=_UTILS_LOGGER):
        discover_actors(client)

    debug_messages = [
        r.getMessage()
        for r in _found_records(caplog)
        if r.levelno == logging.DEBUG
    ]
    assert len(debug_messages) == 3, "Expected one DEBUG dump per actor"
    assert any("Finn the Finder" in m for m in debug_messages)
