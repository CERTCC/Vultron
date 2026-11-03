"""A ``VOCABULARY`` key is never read as an inbound AS2 ``type`` value.

``VOCABULARY`` is keyed by wire class name (``as_Activity``), and a class name
is never an AS2 ``type`` value. Every key is tried here as the ``type`` of an
inbound activity and as a type lookup, and each one is refused. Before #5738
``"type": "as_Activity"`` resolved, because the type lookup fell back to
``VOCABULARY`` and ``as_Activity.type_`` is a bare ``str``.

Spec: `specs/vocabulary-model.yaml` VM-01-016.
"""

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

import importlib
import pkgutil

import pytest

import vultron.wire.as2.vocab as _vocab
from vultron.wire.as2.errors import VultronParseUnknownTypeError
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.registry import (
    VOCABULARY,
    find_in_vocabulary,
)

#: Lower bound on registry size, so a broken import cannot make the test pass
#: vacuously: registration is a submodule import side effect (VM-01-005).
_MIN_REGISTERED_TYPES = 50


def _vocabulary_keys() -> list[str]:
    """Every ``VOCABULARY`` key, once every vocabulary submodule is imported."""
    for module in pkgutil.walk_packages(
        _vocab.__path__, f"{_vocab.__name__}."
    ):
        importlib.import_module(module.name)
    keys = sorted(VOCABULARY)
    assert len(keys) >= _MIN_REGISTERED_TYPES, keys
    return keys


_KEYS = _vocabulary_keys()


@pytest.mark.spec("VM-01-016")
@pytest.mark.parametrize("key", _KEYS)
def test_parse_activity_refuses_a_vocabulary_key_as_the_type(key: str) -> None:
    body = {
        "type": key,
        "id": "https://example.org/activities/1",
        "actor": "https://example.org/actors/alice",
        "object": "https://example.org/objects/1",
        "published": "2026-01-01T00:00:00+00:00",
    }
    with pytest.raises(VultronParseUnknownTypeError):
        parse_activity(body)


@pytest.mark.spec("VM-01-016")
@pytest.mark.parametrize("include_core", [False, True])
@pytest.mark.parametrize("key", _KEYS)
def test_type_lookup_refuses_a_vocabulary_key(
    key: str, include_core: bool
) -> None:
    with pytest.raises(KeyError):
        find_in_vocabulary(key, include_core=include_core)


@pytest.mark.spec("VM-01-016")
def test_the_type_value_of_as_activity_still_resolves() -> None:
    """The class stays reachable by its wire ``type`` value (VM-01-008)."""
    assert find_in_vocabulary("Activity") is VOCABULARY["as_Activity"]
