#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Golden OpenAPI snapshot of the trigger and demo endpoints (TRIG-12-003).

The committed file ``openapi_trigger_snapshot.json`` next to this module
freezes the client-visible trigger API contract: every path under
``/actors/{actor_id}/trigger/`` and ``/actors/{actor_id}/demo/`` exactly as
``app.openapi()`` renders it — ``operation_id``, status codes, summary,
description, request and response schemas — plus every component schema those
operations reference, directly or transitively.  It is captured with
``run_mode=PROTOTYPE`` so the demo router is mounted (TRIG-09-001).

**A red test here is a report that the contract moved.**  The fix is to make
the contract stop moving, or to decide — in review, with the diff in front of
the reviewer — that the move is intended.  Regenerating the snapshot is that
reviewed decision, never a way to turn the test green.  When the move is
intended, regenerate with the single documented command and commit the
result in the same PR as the route change so the diff shows what moved::

    PYTHONPATH= uv run python -m \\
        test.adapters.driving.fastapi.test_openapi_trigger_snapshot

The snapshot's first commit predates any trigger route rewrite (ADR-0110
§ "Migration order"): it freezes the shipped contract, not whatever a rewrite
happened to emit.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, JsonValue

from vultron.adapters.driving.fastapi.app import create_app
from vultron.config import config_override

SNAPSHOT_PATH = Path(__file__).with_name("openapi_trigger_snapshot.json")

#: Path fragments that select the frozen route families (TRIG-08-003,
#: TRIG-08-004).  Matched as substrings so the ``/api/v2`` mount prefix does
#: not have to be repeated here.
TRIGGER_PATH_FRAGMENT = "/actors/{actor_id}/trigger/"
DEMO_PATH_FRAGMENT = "/actors/{actor_id}/demo/"
FROZEN_PATH_FRAGMENTS = (TRIGGER_PATH_FRAGMENT, DEMO_PATH_FRAGMENT)

_SCHEMA_REF_PREFIX = "#/components/schemas/"


def is_frozen_path(path: str) -> bool:
    """True when ``path`` belongs to a route family the snapshot freezes."""
    return any(fragment in path for fragment in FROZEN_PATH_FRAGMENTS)


class SnapshotComponents(BaseModel):
    """The ``components`` slice of the snapshot: referenced schemas only."""

    model_config = ConfigDict(extra="forbid")

    schemas: dict[str, JsonValue]


class TriggerContractSnapshot(BaseModel):
    """The frozen contract: selected ``paths`` and the schemas they reach.

    Structured as the matching slice of an OpenAPI document so the committed
    file reads like one (CS-17-001).
    """

    model_config = ConfigDict(extra="forbid")

    paths: dict[str, JsonValue]
    components: SnapshotComponents


def _collect_schema_refs(node: JsonValue, into: set[str]) -> None:
    """Add every ``#/components/schemas/<Name>`` reachable in ``node``."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                if value.startswith(_SCHEMA_REF_PREFIX):
                    into.add(value.removeprefix(_SCHEMA_REF_PREFIX))
            else:
                _collect_schema_refs(value, into)
    elif isinstance(node, list):
        for item in node:
            _collect_schema_refs(item, into)


def _referenced_schemas(
    paths: dict[str, JsonValue], all_schemas: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    """Return the schemas the selected paths reference, transitively."""
    pending: set[str] = set()
    for path_item in paths.values():
        _collect_schema_refs(path_item, pending)
    selected: dict[str, JsonValue] = {}
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        selected[name] = all_schemas[name]
        nested: set[str] = set()
        _collect_schema_refs(selected[name], nested)
        pending.update(nested - selected.keys())
    return dict(sorted(selected.items()))


def trigger_contract(document: dict[str, Any]) -> TriggerContractSnapshot:
    """Slice the trigger and demo route families out of an OpenAPI document.

    Args:
        document: The full document ``FastAPI.openapi()`` returned.

    Returns:
        The frozen contract: every path containing one of
        :data:`FROZEN_PATH_FRAGMENTS`, and every component schema those
        paths reference directly or through another referenced schema.
    """
    all_paths: dict[str, JsonValue] = document["paths"]
    paths = {
        path: item
        for path, item in sorted(all_paths.items())
        if is_frozen_path(path)
    }
    all_schemas: dict[str, JsonValue] = document["components"]["schemas"]
    return TriggerContractSnapshot(
        paths=paths,
        components=SnapshotComponents(
            schemas=_referenced_schemas(paths, all_schemas)
        ),
    )


def build_prototype_app() -> FastAPI:
    """Build an isolated app with the demo router mounted (TRIG-09-001).

    Forces ``run_mode=PROTOTYPE`` for the duration of construction so the
    result does not depend on the caller's environment; ``config_override``
    restores the config cache on exit (CFG-06-006).
    """
    with config_override(VULTRON_MODE="prototype"):
        return create_app(docs_url=None, openapi_url=None)


def live_contract() -> TriggerContractSnapshot:
    """The contract the shipped routes render right now."""
    return trigger_contract(build_prototype_app().openapi())


def canonical_json(snapshot: TriggerContractSnapshot) -> str:
    """One stable rendering, so a diff shows only what moved."""
    payload = snapshot.model_dump(mode="json")
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def load_committed_snapshot() -> TriggerContractSnapshot:
    """Read the committed golden file."""
    return TriggerContractSnapshot.model_validate_json(
        SNAPSHOT_PATH.read_text(encoding="utf-8")
    )


def write_snapshot(path: Path = SNAPSHOT_PATH) -> None:
    """Write the live contract to ``path`` in canonical form.

    With the default ``path`` this is the body of the documented regeneration
    command.  Run it only as a reviewed decision that the contract is meant
    to move; see the module docstring.
    """
    path.write_text(canonical_json(live_contract()), encoding="utf-8")


def _contract_diff(
    committed: TriggerContractSnapshot, live: TriggerContractSnapshot
) -> list[str]:
    return list(
        difflib.unified_diff(
            canonical_json(committed).splitlines(),
            canonical_json(live).splitlines(),
            fromfile=f"committed {SNAPSHOT_PATH.name}",
            tofile="live app.openapi()",
            lineterm="",
        )
    )


@pytest.fixture(scope="module")
def live() -> TriggerContractSnapshot:
    """The live contract, built once per module: app construction is slow."""
    return live_contract()


@pytest.mark.spec("TRIG-12-003")
def test_trigger_openapi_contract_matches_committed_snapshot(
    live: TriggerContractSnapshot,
) -> None:
    """The live trigger and demo contract is byte-for-byte the golden file.

    A failure lists exactly what moved as a unified diff.  Do not regenerate
    the snapshot to silence it: regeneration is a reviewed decision that the
    contract is meant to change (module docstring), never a fix for a red
    test.
    """
    diff = _contract_diff(load_committed_snapshot(), live)
    assert not diff, (
        "Trigger API contract differs from the committed golden snapshot "
        "(TRIG-12-003). This is a contract change, not a test failure to "
        "silence: either undo the change, or regenerate the snapshot as a "
        "reviewed decision and commit it with the route change.\n"
        + "\n".join(diff)
    )


@pytest.mark.spec("TRIG-12-003")
def test_committed_snapshot_is_canonical() -> None:
    """The golden file is the regeneration command's exact output.

    A hand edit that reorders keys or changes whitespace would still compare
    equal as a document but make the next regeneration show a spurious diff;
    pinning the bytes keeps every future diff about the contract.
    """
    committed_text = SNAPSHOT_PATH.read_text(encoding="utf-8")
    assert committed_text == canonical_json(load_committed_snapshot())


@pytest.mark.spec("TRIG-09-001")
def test_live_contract_covers_both_route_families(
    live: TriggerContractSnapshot,
) -> None:
    """Both frozen families are present, proving the demo router is mounted.

    Guards the snapshot against going quietly demo-less if PROTOTYPE mounting
    regressed: the equality test would also fail, but this names the cause.
    """
    families_present = {
        fragment: any(fragment in path for path in live.paths)
        for fragment in FROZEN_PATH_FRAGMENTS
    }
    assert families_present == {
        TRIGGER_PATH_FRAGMENT: True,
        DEMO_PATH_FRAGMENT: True,
    }


def test_write_snapshot_emits_the_canonical_live_contract(
    live: TriggerContractSnapshot, tmp_path: Path
) -> None:
    """The regeneration command writes exactly what the equality test reads.

    Pins the writer to the same canonical rendering the comparison uses, so
    a regenerated file is green by construction and a diff is never about
    formatting.
    """
    target = tmp_path / SNAPSHOT_PATH.name
    write_snapshot(target)
    assert target.read_text(encoding="utf-8") == canonical_json(live)


if __name__ == "__main__":
    # The documented regeneration command (module docstring).
    write_snapshot()
    print(f"wrote {SNAPSHOT_PATH}")
