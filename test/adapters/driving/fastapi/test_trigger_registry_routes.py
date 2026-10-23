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

"""Route-to-registry bijection and exposure (TRIG-12-004, TRIG-08-003/004).

Every ``POST`` route mounted under ``/actors/{actor_id}/trigger/`` or
``/actors/{actor_id}/demo/`` has exactly one registry row whose ``verb`` is
its final path segment and whose ``exposure`` names the prefix it sits under,
and every row has such a route — exact set equality in both directions
(ARCH-18-001).  This is the executable form of the verification clauses on
TRIG-08-003 and TRIG-08-004, which until the registry existed read
"inspection confirms".

The mounted routes are read from the OpenAPI document the app renders — the
same document the golden snapshot freezes (TRIG-12-003) — built with the demo
router mounted (``run_mode=PROTOTYPE``) so the demo-only rows are visible
(TRIG-09-001).  Two ``GET`` routes also live under ``/demo/`` — the case-ledger
read endpoints — and are not triggers; they are pinned by name so a third
non-trigger route under either prefix is noticed rather than silently excluded.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute

from test.adapters.driving.fastapi.test_openapi_trigger_snapshot import (
    DEMO_PATH_FRAGMENT,
    TRIGGER_PATH_FRAGMENT,
    build_prototype_app,
    is_frozen_path,
)
from vultron.trigger_registry import TriggerExposure, entries, lookup_entry

#: Reads under ``/demo/`` that are not triggers (SYNC-01-002, TRIG-09-001).
_KNOWN_NON_TRIGGER_ROUTES = frozenset(
    {
        ("GET", "/api/v2/actors/{actor_id}/demo/cases/{case_id}/log"),
        ("GET", "/api/v2/actors/{actor_id}/demo/cases/{case_id}/log/{index}"),
        ("GET", "/api/v2/actors/{actor_id}/demo/cases/{case_id}/log/stream"),
    }
)

_FRAGMENT_TO_EXPOSURE = {
    TRIGGER_PATH_FRAGMENT: TriggerExposure.GENERAL_PURPOSE,
    DEMO_PATH_FRAGMENT: TriggerExposure.DEMO_ONLY,
}


@pytest.fixture(scope="module")
def app() -> FastAPI:
    """The prototype app, built once: construction is slow."""
    return build_prototype_app()


@pytest.fixture(scope="module")
def paths(app: FastAPI) -> dict[str, Any]:
    """``paths`` of the prototype app's OpenAPI document."""
    document: dict[str, Any] = app.openapi()
    paths: dict[str, Any] = document["paths"]
    return paths


def _mounted(paths: dict[str, Any]) -> set[tuple[str, str]]:
    """``(METHOD, path)`` for every operation under either prefix."""
    return {
        (method.upper(), path)
        for path, item in paths.items()
        if any(f in path for f in _FRAGMENT_TO_EXPOSURE)
        for method in item
    }


def trigger_routes(
    paths: dict[str, Any],
) -> dict[tuple[TriggerExposure, str], str]:
    """``(exposure, verb)`` → path for every POST under either prefix."""
    found: dict[tuple[TriggerExposure, str], str] = {}
    for method, path in _mounted(paths):
        if method != "POST":
            continue
        exposure = next(
            exp for f, exp in _FRAGMENT_TO_EXPOSURE.items() if f in path
        )
        key = (exposure, path.rsplit("/", 1)[-1])
        assert key not in found, f"two POST routes share {key}"
        found[key] = path
    return found


@pytest.mark.spec("TRIG-12-004")
@pytest.mark.spec("TRIG-08-003")
@pytest.mark.spec("TRIG-08-004")
def test_trigger_routes_and_registry_rows_are_in_bijection(
    paths: dict[str, Any],
) -> None:
    """Exact equality: mounted ``(prefix, verb)`` == registry ``(exposure, verb)``."""
    mounted = set(trigger_routes(paths))
    registered = {(row.exposure, row.verb) for row in entries()}
    assert mounted == registered, (
        "trigger routes and registry rows disagree.\n"
        "  mounted, no row:   "
        f"{sorted((e.value, v) for e, v in mounted - registered)}\n"
        "  row, not mounted:  "
        f"{sorted((e.value, v) for e, v in registered - mounted)}"
    )


@pytest.mark.spec("TRIG-08-003")
@pytest.mark.spec("TRIG-08-004")
@pytest.mark.parametrize("exposure", list(TriggerExposure), ids=str)
def test_every_row_is_mounted_under_its_exposures_prefix(
    paths: dict[str, Any], exposure: TriggerExposure
) -> None:
    """General-purpose rows under ``/trigger/`` only, demo-only under ``/demo/``
    only — each row's path carries its own prefix and not the other's."""
    routes = trigger_routes(paths)
    own = next(
        f for f, exp in _FRAGMENT_TO_EXPOSURE.items() if exp is exposure
    )
    others = [f for f in _FRAGMENT_TO_EXPOSURE if f != own]
    rows = [row for row in entries() if row.exposure is exposure]
    assert rows, f"no rows with exposure {exposure}"
    for row in rows:
        path = routes[(row.exposure, row.verb)]
        assert own in path, path
        assert not any(other in path for other in others), path


@pytest.mark.spec("TRIG-12-004")
def test_every_mounted_verb_looks_up_to_its_row(paths: dict[str, Any]) -> None:
    """The lookup function answers for each mounted verb with the same row the
    enumeration carries — one table, two views."""
    for (exposure, verb), path in trigger_routes(paths).items():
        row = lookup_entry(verb)
        assert row.exposure is exposure, (path, row)


@pytest.mark.spec("TRIG-09-001")
def test_only_the_known_ledger_reads_are_non_trigger_routes(
    paths: dict[str, Any],
) -> None:
    """Every non-POST operation under either prefix is one of the ledger GETs.

    Pins the exclusion the bijection relies on: a new non-trigger route under
    ``/trigger/`` or ``/demo/`` shows up here instead of being skipped.
    """
    non_post = {(m, p) for m, p in _mounted(paths) if m != "POST"}
    assert non_post == set(_KNOWN_NON_TRIGGER_ROUTES)


def _api_routes(routes: Iterable[BaseRoute]) -> Iterator[APIRoute]:
    """Every ``APIRoute`` leaf, through included routers.

    ``include_router`` registers a wrapper that holds the original router, so
    the leaves are not on ``app.routes`` directly; this descends until it finds
    them.  Paths come back without the mount prefix, which ``is_frozen_path``
    does not need.
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
            continue
        nested: Iterable[BaseRoute] | None = getattr(
            getattr(route, "original_router", None), "routes", None
        ) or getattr(route, "routes", None)
        if nested is not None:
            yield from _api_routes(nested)


def _trigger_api_routes(app: FastAPI) -> list[APIRoute]:
    """Every mounted ``POST`` under ``/trigger/`` or ``/demo/``."""
    return [
        r
        for r in _api_routes(app.routes)
        if is_frozen_path(r.path) and "POST" in (r.methods or set())
    ]


@pytest.mark.spec("TRIG-12-001")
def test_every_trigger_route_declares_a_response_model(app: FastAPI) -> None:
    """A route without a ``response_model`` describes no response body in the
    OpenAPI document; exact equality so none can be missing or extra."""
    routes = _trigger_api_routes(app)
    assert len(routes) == len(entries())
    missing = sorted(r.path for r in routes if r.response_model is None)
    assert missing == []


@pytest.mark.spec("TRIG-12-001")
@pytest.mark.spec("TRIG-12-004")
def test_every_trigger_route_response_model_is_its_rows_result_type(
    app: FastAPI,
) -> None:
    """The declared ``response_model`` is the registry row's ``result_type``
    — the same class, so OpenAPI and the pinned key set cannot drift apart."""
    mismatched = {
        r.path: (
            getattr(r.response_model, "__name__", r.response_model),
            lookup_entry(r.path.rsplit("/", 1)[-1]).result_type.__name__,
        )
        for r in _trigger_api_routes(app)
        if r.response_model
        is not lookup_entry(r.path.rsplit("/", 1)[-1]).result_type
    }
    assert mismatched == {}
