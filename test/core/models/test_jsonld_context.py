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
"""The one rule placing ``@context`` on the top-level document (VM-10-005).

The roots' serializers are covered through real objects elsewhere
(``test/adapters/test_outbound_vultron_context.py``); these tests pin the
branches of the shared helper that no object reaches on its own.
"""

from dataclasses import dataclass
from typing import Any, cast

import pytest
from pydantic import SerializationInfo

from vultron.core.models.base.context import (
    DEFAULT_JSONLD_CONTEXT,
    default_jsonld_context,
    is_default_jsonld_context,
    serialize_with_top_level_context,
)


@dataclass
class _Info:
    by_alias: bool


def _info(by_alias: bool = True) -> SerializationInfo:
    return cast(SerializationInfo, _Info(by_alias=by_alias))


def _dump(explicit: Any = None, *, by_alias: bool = True) -> Any:
    return serialize_with_top_level_context(
        lambda: {"type": "Note", "@context": "urn:x:stale"},
        _info(by_alias),
        explicit,
    )


def test_a_top_level_document_gets_the_default_list_first():
    dumped = _dump()

    assert list(dumped) == ["@context", "type"]
    assert dumped["@context"] == list(DEFAULT_JSONLD_CONTEXT)


def test_the_persistence_dump_is_passed_through_untouched():
    assert _dump(by_alias=False) == {"type": "Note", "@context": "urn:x:stale"}


def test_a_non_mapping_dump_is_passed_through():
    result = serialize_with_top_level_context(lambda: "bare", _info(), None)

    assert result == "bare"


@pytest.mark.spec("VM-10-005")
def test_a_nested_object_drops_the_default_and_keeps_an_explicit_context():
    def outer() -> dict[str, Any]:
        return {
            "type": "Create",
            "object": _dump(),
            "target": _dump(["urn:x:own"]),
        }

    dumped = serialize_with_top_level_context(outer, _info(), None)

    assert "@context" not in dumped["object"]
    assert dumped["target"]["@context"] == ["urn:x:own"]
    assert dumped["@context"] == list(DEFAULT_JSONLD_CONTEXT)


def test_a_failed_dump_leaves_the_next_one_top_level():
    def boom() -> dict[str, Any]:
        raise RuntimeError("dump failed")

    with pytest.raises(RuntimeError):
        serialize_with_top_level_context(boom, _info(), None)

    assert _dump()["@context"] == list(DEFAULT_JSONLD_CONTEXT)


def test_the_default_list_is_fresh_and_recognised_only_in_order():
    first = default_jsonld_context()
    first.append("urn:x:extra")

    assert default_jsonld_context() == list(DEFAULT_JSONLD_CONTEXT)
    assert is_default_jsonld_context(list(DEFAULT_JSONLD_CONTEXT))
    assert not is_default_jsonld_context(
        list(reversed(DEFAULT_JSONLD_CONTEXT))
    )
    assert not is_default_jsonld_context(DEFAULT_JSONLD_CONTEXT)
    assert not is_default_jsonld_context(DEFAULT_JSONLD_CONTEXT[1])
