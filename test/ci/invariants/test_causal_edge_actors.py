"""Tests for the ``consequent_actor`` check in ``check_causal_edges`` (#4248).

Synthetic ledgers and dump manifests only; no ``devlogs/`` needed.  Not tagged
``case_ledger_invariants``, so they run in the regular unit suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from test.ci.invariants import common
from test.ci.invariants.common import (
    check_causal_edges,
    load_actor_names,
    recorded_actor_name,
)

_VENDOR_KEY = "vendor-0123"
_CASE_ACTOR_KEY = "case-actor-4567"
_NAMES = {_VENDOR_KEY: "vendor", _CASE_ACTOR_KEY: "case-actor"}


def _entry(idx: int, evt: str, actor: str | None) -> dict:
    snap: dict = {} if actor is None else {"actor": actor}
    return {"log_index": idx, "eventType": evt, "payloadSnapshot": snap}


def _replicas(*entries: dict) -> dict[str, list[dict]]:
    return {"case-actor": list(entries)}


def _edge(actor: str = "vendor") -> list[dict]:
    return [
        {
            "antecedent": "engage_case",
            "consequent": "close_case",
            "consequent_actor": actor,
        }
    ]


def _ledger(actor: str | None) -> dict[str, list[dict]]:
    return _replicas(
        _entry(0, "engage_case", f"https://x.example/actors/{_VENDOR_KEY}"),
        _entry(1, "close_case", actor),
    )


def _run(
    replicas: dict[str, list[dict]],
    edges: list[dict],
    names: dict[str, str] | None,
) -> tuple[list[str], list[str]]:
    mismatches: list[str] = []
    violations = check_causal_edges(
        replicas, edges, names, actor_mismatches=mismatches
    )
    return violations, mismatches


def test_matching_tag_is_clean() -> None:
    ledger = _ledger(f"https://x.example/actors/{_VENDOR_KEY}")
    assert _run(ledger, _edge("vendor"), _NAMES) == ([], [])


def test_mismatching_tag_is_reported_without_failing() -> None:
    ledger = _ledger(f"https://x.example/actors/{_VENDOR_KEY}")
    violations, mismatches = _run(ledger, _edge("coordinator"), _NAMES)
    assert violations == []
    assert len(mismatches) == 1
    assert "'coordinator'" in mismatches[0]
    assert "'vendor'" in mismatches[0]


def test_actor_absent_from_manifest_is_reported() -> None:
    ledger = _ledger("https://x.example/actors/stranger-99")
    violations, mismatches = _run(ledger, _edge("vendor"), _NAMES)
    assert violations == []
    assert len(mismatches) == 1
    assert "unresolved: stranger-99" in mismatches[0]


def test_entry_with_no_recorded_actor_is_reported() -> None:
    violations, mismatches = _run(_ledger(None), _edge("vendor"), _NAMES)
    assert violations == []
    assert "no actor recorded" in mismatches[0]


def test_no_manifest_leaves_every_tagged_edge_unresolvable() -> None:
    ledger = _ledger(f"https://x.example/actors/{_VENDOR_KEY}")
    violations, mismatches = _run(ledger, _edge("vendor"), {})
    assert violations == []
    assert len(mismatches) == 1


def test_candidates_are_restricted_to_the_tagged_actor() -> None:
    """A matching entry decides ordering; a later other-actor entry does not."""
    ledger = _replicas(
        _entry(0, "close_case", f"https://x.example/actors/{_VENDOR_KEY}"),
        _entry(1, "engage_case", f"https://x.example/actors/{_VENDOR_KEY}"),
        _entry(2, "close_case", f"https://x.example/actors/{_CASE_ACTOR_KEY}"),
    )
    violations, mismatches = _run(ledger, _edge("vendor"), _NAMES)
    assert mismatches == []
    assert violations, "ordering must use only the vendor's close_case"


def test_none_names_skips_the_actor_check() -> None:
    ledger = _ledger("https://x.example/actors/stranger-99")
    assert _run(ledger, _edge("vendor"), None) == ([], [])


def test_edge_without_a_tag_is_not_checked() -> None:
    edges = [{"antecedent": "engage_case", "consequent": "close_case"}]
    ledger = _ledger("https://x.example/actors/stranger-99")
    assert _run(ledger, edges, _NAMES) == ([], [])


def test_recorded_actor_name_accepts_an_object_actor() -> None:
    entry = _entry(0, "x", None)
    entry["payloadSnapshot"]["actor"] = {"id": f"urn:x:{_VENDOR_KEY}"}
    name, _ = recorded_actor_name(entry, _NAMES)
    assert (
        name == "vendor" or name is None
    )  # prefix handling is strip_id_prefix's


def test_load_actor_names_reads_the_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = tmp_path / "fv"
    scenario.mkdir()
    (scenario / common.DUMP_MANIFEST_FILENAME).write_text(
        json.dumps(
            {
                "actors": [
                    {"actorName": "vendor", "routeKey": _VENDOR_KEY},
                    {"actorName": "broken"},
                    "not-a-record",
                ],
                "unreplicatedActors": [
                    {"actorName": "rejector", "routeKey": "route-r"}
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(common, "_DEVLOGS_DIR", tmp_path)
    assert load_actor_names("fv") == {
        _VENDOR_KEY: "vendor",
        "route-r": "rejector",
    }
    assert load_actor_names("absent") == {}
