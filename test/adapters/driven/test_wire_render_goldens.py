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

"""Golden render output for every ``CORE_VOCABULARY`` entry (#3490 AC-2).

The goldens were captured from ``As2WireRenderAdapter.render()`` *before* it
stopped resolving a wire counterpart (ADR-0099 detail 1), so this test is the
evidence that the one-object-model render is a behaviour-preserving change.
The ``VultronNote`` and ``VultronActivity``-family entries were added after:
the port refused them until ADR-0099 detail 4 moved them onto ``CoreObject``.
Later ``main`` changes were then regenerated in: ``CoreActorCollection`` was
deleted (#3563), and actors now derive an absent inbox/outbox from their id
(#3616).

Two value classes are generated afresh on every construction by nested
defaults and are normalised before comparison: minted ``urn:uuid:`` ids and
wall-clock timestamps.  Every timestamp the fixture pins is compared exactly.

Regenerate (only when a render change is intended and reviewed)::

    PYTHONPATH=. uv run python test/adapters/driven/test_wire_render_goldens.py
"""

import json
import re
from functools import cache
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from test.support.core_vocab import build_core_vocab
from vultron.adapters.driven.wire_render import As2WireRenderAdapter

GOLDEN_PATH = Path(__file__).parent / "golden" / "wire_render_core_vocab.json"

_PINNED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
_PINNED_PREFIX = "2026-01-02T03:04:05"
_UUID_URN = re.compile(r"urn:uuid:[0-9a-f-]{36}")
_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?"
)


def _normalise(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalise(v) for v in value]
    if isinstance(value, str):
        value = _UUID_URN.sub("urn:uuid:<minted>", value)
        return _TIMESTAMP.sub(
            lambda m: (
                m.group(0)
                if m.group(0).startswith(_PINNED_PREFIX)
                else "<clock>"
            ),
            value,
        )
    return value


@cache
def _render_all() -> dict[str, Any]:
    built, unconstructible = build_core_vocab(
        "golden", {"published": _PINNED, "updated": _PINNED}
    )
    assert not unconstructible, (
        "every CORE_VOCABULARY entry must be covered by the render goldens; "
        f"could not construct: {unconstructible}"
    )
    adapter = As2WireRenderAdapter()
    return {name: _normalise(adapter.render(obj)) for name, obj in built}


def _golden() -> dict[str, Any]:
    golden: dict[str, Any] = json.loads(GOLDEN_PATH.read_text())
    return golden


def test_goldens_cover_every_core_vocabulary_entry() -> None:
    assert set(_render_all()) == set(_golden())


@pytest.mark.parametrize("name", sorted(_render_all()))
def test_render_matches_golden(name: str) -> None:
    assert _render_all()[name] == _golden()[name]


if __name__ == "__main__":
    GOLDEN_PATH.parent.mkdir(exist_ok=True)
    GOLDEN_PATH.write_text(
        json.dumps(_render_all(), indent=2, sort_keys=True) + "\n"
    )
    print(f"wrote {GOLDEN_PATH}")
