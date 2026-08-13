"""Negative-case tests for every invariant check function in common.py.

Each test confirms that a deliberate violation is detected (non-empty
violation list returned).  The synthetic fixtures in conftest.py supply
the valid baseline; each test modifies that baseline to inject one
specific fault.

AC-1 of ISSUE-1976.
"""

from __future__ import annotations

import hashlib
import json

import pytest
from _pytest.outcomes import Failed, Skipped

from test.ci.invariants import common
from test.ci.invariants.common import (
    check_cross_actor_hash_agreement,
    check_cross_actor_payload_actor_agreement,
    check_cs_state_transitions_observed,
    check_event_type_count,
    check_event_type_present,
    check_genesis_entry_present,
    check_hash_chain,
    check_late_joiner_has_full_history,
    check_log_starts_at_genesis,
    check_nested_objects_inlined,
    check_no_gaps_in_log_indices,
    check_no_rm_state_oscillation,
    check_non_empty_payload_snapshots,
    check_participant_status_schema_completeness,
    check_payload_context_uses_case_uri,
    check_rm_closed_termination,
)
from vultron.demo.helpers.ledger_dump import DUMP_MANIFEST_FILENAME

CASE_URI = "https://example.org/cases/test-case"
_SHA256 = lambda s: hashlib.sha256(s.encode()).hexdigest()  # noqa: E731
GENESIS_HASH = _SHA256("genesis")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(
    log_index: int,
    entry_hash: str,
    prev_log_hash: str,
    event_type: str = "noop",
    payload: dict | None = None,
) -> dict:
    return {
        "logIndex": log_index,
        "entryHash": entry_hash,
        "prevLogHash": prev_log_hash,
        "eventType": event_type,
        "case_id": CASE_URI,
        "payloadSnapshot": payload or {},
        "disposition": "recorded",
    }


def _simple_two_entry_chain(actor: str = "case-actor") -> list[dict]:
    h0 = _SHA256(f"{actor}:0")
    h1 = _SHA256(f"{actor}:1")
    return [
        _entry(0, h0, GENESIS_HASH),
        _entry(1, h1, h0),
    ]


# ---------------------------------------------------------------------------
# Invariant 1: check_hash_chain
# ---------------------------------------------------------------------------


def test_check_hash_chain_detects_broken_link():
    broken = _simple_two_entry_chain()
    broken[1]["prevLogHash"] = "a" * 64  # wrong hash
    violations = check_hash_chain("case-actor", broken)
    assert violations


def test_check_hash_chain_detects_missing_entry_hash():
    chain = _simple_two_entry_chain()
    chain[0]["entryHash"] = ""
    violations = check_hash_chain("case-actor", chain)
    assert violations


def test_check_hash_chain_detects_invalid_genesis_prev_hash():
    chain = _simple_two_entry_chain()
    chain[0]["prevLogHash"] = "not-a-hex-hash"
    violations = check_hash_chain("case-actor", chain)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 2: check_cross_actor_hash_agreement
# ---------------------------------------------------------------------------


def test_check_cross_actor_hash_agreement_detects_disagreement():
    h0 = _SHA256("actor-a:0")
    entry_a = _entry(0, h0, GENESIS_HASH)
    entry_b = _entry(0, _SHA256("different"), GENESIS_HASH)
    replicas = {"actor-a": [entry_a], "actor-b": [entry_b]}
    violations = check_cross_actor_hash_agreement(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 3: check_cross_actor_payload_actor_agreement
# ---------------------------------------------------------------------------


def test_check_cross_actor_payload_actor_agreement_detects_disagreement():
    h0 = _SHA256("shared:0")
    entry_a = _entry(0, h0, GENESIS_HASH, payload={"actor": "alice"})
    entry_b = _entry(0, h0, GENESIS_HASH, payload={"actor": "bob"})
    replicas = {"actor-a": [entry_a], "actor-b": [entry_b]}
    violations = check_cross_actor_payload_actor_agreement(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 4: check_non_empty_payload_snapshots
# ---------------------------------------------------------------------------


def test_check_non_empty_payload_snapshots_detects_empty_payload():
    h0 = _SHA256("x:0")
    entry = _entry(0, h0, GENESIS_HASH, payload={})
    entry["disposition"] = "recorded"
    replicas = {"case-actor": [entry]}
    violations = check_non_empty_payload_snapshots(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 5a: check_event_type_present
# ---------------------------------------------------------------------------


def test_check_event_type_present_returns_violation_when_absent():
    h0 = _SHA256("ev:0")
    entry = _entry(0, h0, GENESIS_HASH, event_type="something_else")
    replicas = {"case-actor": [entry]}
    violations = check_event_type_present(replicas, "missing_event_type")
    assert violations


# ---------------------------------------------------------------------------
# Invariant 5b: check_event_type_count
# ---------------------------------------------------------------------------


def test_check_event_type_count_returns_violation_when_below_min():
    h0 = _SHA256("ev:0")
    entry = _entry(
        0, h0, GENESIS_HASH, event_type="add_participant_status_to_participant"
    )
    replicas = {"case-actor": [entry]}
    violations = check_event_type_count(
        replicas, "add_participant_status_to_participant", 3
    )
    assert violations


# ---------------------------------------------------------------------------
# Invariant 6: check_no_rm_state_oscillation
# ---------------------------------------------------------------------------


def test_check_no_rm_state_oscillation_detects_post_closed_transition():
    actor_id = "https://example.org/actors/a"
    h0, h1 = (_SHA256(f"osc:{i}") for i in range(2))
    entries = [
        _entry(
            0,
            h0,
            GENESIS_HASH,
            event_type="add_participant_status_to_participant",
            payload={
                "object": {
                    "attributedTo": actor_id,
                    "rmState": "CLOSED",
                    "emConsentState": "SIGNATORY",
                    "cvdRole": ["FINDER"],
                }
            },
        ),
        _entry(
            1,
            h1,
            h0,
            event_type="add_participant_status_to_participant",
            payload={
                "object": {
                    "attributedTo": actor_id,
                    "rmState": "ACCEPTED",  # post-CLOSED → oscillation
                    "emConsentState": "SIGNATORY",
                    "cvdRole": ["FINDER"],
                }
            },
        ),
    ]
    replicas = {"case-actor": entries}
    violations = check_no_rm_state_oscillation(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 7: check_rm_closed_termination
# ---------------------------------------------------------------------------


def test_check_rm_closed_termination_detects_open_participant():
    actor_id = "https://example.org/actors/open"
    h0 = _SHA256("open:0")
    entry = _entry(
        0,
        h0,
        GENESIS_HASH,
        event_type="add_participant_status_to_participant",
        payload={
            "object": {
                "attributedTo": actor_id,
                "rmState": "ACCEPTED",  # not CLOSED
                "emConsentState": "SIGNATORY",
                "cvdRole": ["FINDER"],
            }
        },
    )
    replicas = {"case-actor": [entry]}
    violations = check_rm_closed_termination(replicas)
    assert violations


def test_check_rm_closed_termination_returns_violation_when_no_status_entries():
    h0 = _SHA256("nostatus:0")
    entry = _entry(
        0, h0, GENESIS_HASH, event_type="create_case", payload={"actor": "x"}
    )
    replicas = {"case-actor": [entry]}
    violations = check_rm_closed_termination(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 8: check_late_joiner_has_full_history
# ---------------------------------------------------------------------------


def test_check_late_joiner_has_full_history_detects_gap(late_joiner_replicas):
    violations = check_late_joiner_has_full_history(
        late_joiner_replicas, early_actor="early", late_actor="late"
    )
    assert violations


def test_check_late_joiner_has_full_history_no_violation_when_complete(
    full_history_replicas,
):
    violations = check_late_joiner_has_full_history(
        full_history_replicas, early_actor="early", late_actor="late"
    )
    assert not violations


# ---------------------------------------------------------------------------
# Invariant 9: check_participant_status_schema_completeness
# ---------------------------------------------------------------------------


def test_check_participant_status_schema_completeness_detects_missing_field():
    h0 = _SHA256("schema:0")
    entry = _entry(
        0,
        h0,
        GENESIS_HASH,
        event_type="add_participant_status_to_participant",
        payload={
            "object": {
                "attributedTo": "https://example.org/actors/x",
                "rmState": "VALID",
                # emConsentState intentionally missing
                "cvdRole": ["FINDER"],
            }
        },
    )
    replicas = {"case-actor": [entry]}
    violations = check_participant_status_schema_completeness(replicas)
    assert violations


def test_check_participant_status_schema_completeness_detects_invalid_role():
    h0 = _SHA256("role:0")
    entry = _entry(
        0,
        h0,
        GENESIS_HASH,
        event_type="add_participant_status_to_participant",
        payload={
            "object": {
                "attributedTo": "https://example.org/actors/x",
                "rmState": "VALID",
                "emConsentState": "SIGNATORY",
                "cvdRole": ["NOT_A_REAL_ROLE"],
            }
        },
    )
    replicas = {"case-actor": [entry]}
    violations = check_participant_status_schema_completeness(replicas)
    assert violations


def test_check_participant_status_schema_completeness_no_status_entries_is_violation():
    h0 = _SHA256("nostatus2:0")
    entry = _entry(
        0, h0, GENESIS_HASH, event_type="create_case", payload={"actor": "x"}
    )
    replicas = {"case-actor": [entry]}
    violations = check_participant_status_schema_completeness(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 10: check_nested_objects_inlined
# ---------------------------------------------------------------------------


def test_check_nested_objects_inlined_detects_bare_id_string():
    h0 = _SHA256("inline:0")
    entry = _entry(
        0,
        h0,
        GENESIS_HASH,
        event_type="add_participant_status_to_participant",
        payload={"object": "https://example.org/objects/bare-id"},
    )
    replicas = {"case-actor": [entry]}
    violations = check_nested_objects_inlined(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 11: check_payload_context_uses_case_uri
# ---------------------------------------------------------------------------


def test_check_payload_context_uses_case_uri_detects_mismatch():
    h0 = _SHA256("ctx:0")
    entry = _entry(
        0,
        h0,
        GENESIS_HASH,
        event_type="create_case",
        payload={"context": "https://example.org/cases/WRONG"},
    )
    entry["case_id"] = CASE_URI
    replicas = {"case-actor": [entry]}
    violations = check_payload_context_uses_case_uri(replicas)
    assert violations


# ---------------------------------------------------------------------------
# Invariant 12: check_genesis_entry_present
# ---------------------------------------------------------------------------


def test_check_genesis_entry_present_detects_missing_genesis():
    h1 = _SHA256("nogenesis:1")
    entry = _entry(1, h1, _SHA256("prev"), event_type="noop")
    violations = check_genesis_entry_present("case-actor", [entry])
    assert violations


def test_check_genesis_entry_present_detects_empty_log():
    violations = check_genesis_entry_present("case-actor", [])
    assert violations


# ---------------------------------------------------------------------------
# Invariant 13: check_log_starts_at_genesis
# ---------------------------------------------------------------------------


def test_check_log_starts_at_genesis_detects_non_zero_start():
    h2 = _SHA256("nzstart:2")
    entry = _entry(2, h2, _SHA256("prev"), event_type="noop")
    violations = check_log_starts_at_genesis("case-actor", [entry])
    assert violations


def test_check_log_starts_at_genesis_detects_empty_log():
    violations = check_log_starts_at_genesis("case-actor", [])
    assert violations


# ---------------------------------------------------------------------------
# Invariant 14: check_no_gaps_in_log_indices
# ---------------------------------------------------------------------------


def test_check_no_gaps_in_log_indices_detects_gap():
    h0 = _SHA256("gap:0")
    entries = [
        _entry(0, h0, GENESIS_HASH),
        _entry(2, _SHA256("gap:2"), h0),  # index 1 is missing
    ]
    violations = check_no_gaps_in_log_indices("case-actor", entries)
    assert violations


def test_check_no_gaps_in_log_indices_detects_empty_log():
    violations = check_no_gaps_in_log_indices("case-actor", [])
    assert violations


# ---------------------------------------------------------------------------
# Invariant 15: check_cs_state_transitions_observed
# ---------------------------------------------------------------------------


def test_check_cs_state_transitions_observed_detects_missing_fix_ready():
    actor_id = "https://example.org/actors/x"
    h0 = _SHA256("csv:0")
    entry = _entry(
        0,
        h0,
        GENESIS_HASH,
        event_type="add_participant_status_to_participant",
        payload={
            "object": {
                "attributedTo": actor_id,
                "rmState": "VALID",
                "emConsentState": "SIGNATORY",
                "cvdRole": ["FINDER"],
                "vfdState": "vfd",  # never VFd or VFD
                "caseStatus": {"pxaState": "Pxa"},
            }
        },
    )
    replicas = {"case-actor": [entry]}
    violations = check_cs_state_transitions_observed(replicas)
    assert violations


def test_check_cs_state_transitions_observed_detects_no_status_entries():
    h0 = _SHA256("csnostatus:0")
    entry = _entry(
        0, h0, GENESIS_HASH, event_type="create_case", payload={"actor": "x"}
    )
    replicas = {"case-actor": [entry]}
    violations = check_cs_state_transitions_observed(replicas)
    assert violations


def test_check_cs_state_transitions_observed_no_vfd_passes_without_fix_ready():
    """check_fix_ready=False skips VFd check — reject-flow scenario regression.

    Reproduces the fcv-reject Invariant 15 failure (issue #2121): a scenario
    where Vendor never participates produces no VFd observation, which triggered
    a spurious violation when check_fix_ready was unconditional.
    """
    actor_id = "https://example.org/actors/coordinator"
    h0 = _SHA256("no-vfd:0")
    entry = _entry(
        0,
        h0,
        GENESIS_HASH,
        event_type="add_participant_status_to_participant",
        payload={
            "object": {
                "attributedTo": actor_id,
                "rmState": "ACCEPTED",
                "emConsentState": "SIGNATORY",
                "cvdRole": ["COORDINATOR"],
                "vfdState": "vfd",  # no vendor → never VFd
                "caseStatus": {"pxaState": "Pxa"},  # P-transition present
            }
        },
    )
    replicas = {"case-actor": [entry]}
    violations = check_cs_state_transitions_observed(
        replicas, check_fix_ready=False
    )
    assert not violations


def test_check_cs_state_transitions_observed_no_vfd_still_requires_published():
    """check_fix_ready=False still enforces the P-transition requirement."""
    actor_id = "https://example.org/actors/coordinator"
    h0 = _SHA256("no-vfd-no-p:0")
    entry = _entry(
        0,
        h0,
        GENESIS_HASH,
        event_type="add_participant_status_to_participant",
        payload={
            "object": {
                "attributedTo": actor_id,
                "rmState": "ACCEPTED",
                "emConsentState": "SIGNATORY",
                "cvdRole": ["COORDINATOR"],
                "vfdState": "vfd",
                "caseStatus": {"pxaState": "pxa"},  # no P yet
            }
        },
    )
    replicas = {"case-actor": [entry]}
    violations = check_cs_state_transitions_observed(
        replicas, check_fix_ready=False
    )
    assert violations


# ---------------------------------------------------------------------------
# Positive-case (happy-path) tests using conftest fixtures
# ---------------------------------------------------------------------------


class TestAllInvariantsPassOnValidChain:
    """Each invariant function returns no violations on a well-formed 5-entry chain.

    Uses the ``single_actor_replicas`` and ``two_actor_replicas`` fixtures from
    conftest.py to confirm that valid data never triggers false-positive violations.
    """

    def test_check_hash_chain_passes_on_valid_chain(
        self, single_actor_replicas
    ):
        entries = single_actor_replicas["case-actor"]
        assert check_hash_chain("case-actor", entries) == []

    def test_check_cross_actor_hash_agreement_passes_on_identical_replicas(
        self, two_actor_replicas
    ):
        assert check_cross_actor_hash_agreement(two_actor_replicas) == []

    def test_check_cross_actor_payload_actor_agreement_passes(
        self, two_actor_replicas
    ):
        assert (
            check_cross_actor_payload_actor_agreement(two_actor_replicas) == []
        )

    def test_check_non_empty_payload_snapshots_passes(
        self, single_actor_replicas
    ):
        assert check_non_empty_payload_snapshots(single_actor_replicas) == []

    def test_check_no_rm_state_oscillation_passes(self, single_actor_replicas):
        assert check_no_rm_state_oscillation(single_actor_replicas) == []

    def test_check_rm_closed_termination_passes(self, single_actor_replicas):
        assert check_rm_closed_termination(single_actor_replicas) == []

    def test_check_participant_status_schema_completeness_passes(
        self, single_actor_replicas
    ):
        assert (
            check_participant_status_schema_completeness(single_actor_replicas)
            == []
        )

    def test_check_nested_objects_inlined_passes(self, single_actor_replicas):
        assert check_nested_objects_inlined(single_actor_replicas) == []

    def test_check_payload_context_uses_case_uri_passes(
        self, single_actor_replicas
    ):
        assert check_payload_context_uses_case_uri(single_actor_replicas) == []

    def test_check_genesis_entry_present_passes(self, single_actor_replicas):
        entries = single_actor_replicas["case-actor"]
        assert check_genesis_entry_present("case-actor", entries) == []

    def test_check_log_starts_at_genesis_passes(self, single_actor_replicas):
        entries = single_actor_replicas["case-actor"]
        assert check_log_starts_at_genesis("case-actor", entries) == []

    def test_check_no_gaps_in_log_indices_passes(self, single_actor_replicas):
        entries = single_actor_replicas["case-actor"]
        assert check_no_gaps_in_log_indices("case-actor", entries) == []

    def test_check_cs_state_transitions_observed_passes(
        self, single_actor_replicas
    ):
        assert check_cs_state_transitions_observed(single_actor_replicas) == []


# ---------------------------------------------------------------------------
# load_devlogs() artifact handling (ISSUE-2239)
# ---------------------------------------------------------------------------


class TestLoadDevlogsManifestHandling:
    """``load_devlogs`` must fail — not skip — once a demo has dumped.

    Before ISSUE-2239, a scenario that died mid-phase uploaded nothing, so the
    invariant harness could not tell "the demo never ran" apart from "the demo
    ran and produced no ledger entries" and skipped in both cases (a false
    green).  The dump now always writes ``dump-manifest.json``, which is the
    evidence that distinguishes the two.
    """

    def test_skips_when_devlogs_dir_is_absent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(common, "_DEVLOGS_DIR", tmp_path / "nope")
        with pytest.raises(Skipped) as excinfo:
            common.load_devlogs("fvv")
        assert "devlogs/" in str(excinfo.value)

    def test_skips_when_scenario_ran_no_dump(self, tmp_path, monkeypatch):
        """No manifest means the dump never ran, so there is nothing to judge."""
        monkeypatch.setattr(common, "_DEVLOGS_DIR", tmp_path)
        (tmp_path / "fvv").mkdir()
        with pytest.raises(Skipped) as excinfo:
            common.load_devlogs("fvv")
        assert "run the" in str(excinfo.value)

    def test_fails_when_manifest_reports_no_ledgers(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(common, "_DEVLOGS_DIR", tmp_path)
        demo_dir = tmp_path / "fvv"
        demo_dir.mkdir()
        (demo_dir / DUMP_MANIFEST_FILENAME).write_text(
            json.dumps(
                {
                    "demoName": "fvv",
                    "caseId": None,
                    "ledgerFileCount": 0,
                    "targetCount": 0,
                    "reason": "The scenario failed before a case existed.",
                    "actors": [],
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(Failed) as excinfo:
            common.load_devlogs("fvv")
        message = excinfo.value.msg or ""
        assert "no case-ledger" in message.lower()
        assert "The scenario failed before a case existed." in message

    def test_failure_message_names_each_missing_actor(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(common, "_DEVLOGS_DIR", tmp_path)
        demo_dir = tmp_path / "fvv"
        demo_dir.mkdir()
        (demo_dir / DUMP_MANIFEST_FILENAME).write_text(
            json.dumps(
                {
                    "demoName": "fvv",
                    "caseId": CASE_URI,
                    "ledgerFileCount": 0,
                    "targetCount": 2,
                    "reason": None,
                    "actors": [
                        {
                            "actorName": "finder",
                            "routeKey": "finder",
                            "captured": False,
                            "entryCount": 0,
                            "ledgerFile": None,
                            "reason": "ValueError: No case ledger entries",
                        },
                        {
                            "actorName": "vendor",
                            "routeKey": "vendor",
                            "captured": False,
                            "entryCount": 0,
                            "ledgerFile": None,
                            "reason": None,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(Failed) as excinfo:
            common.load_devlogs("fvv")
        message = excinfo.value.msg or ""
        assert "finder" in message
        assert "ValueError: No case ledger entries" in message
        assert "vendor" in message

    def test_fails_when_manifest_is_unreadable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(common, "_DEVLOGS_DIR", tmp_path)
        demo_dir = tmp_path / "fvv"
        demo_dir.mkdir()
        (demo_dir / DUMP_MANIFEST_FILENAME).write_text(
            "{not json", encoding="utf-8"
        )
        with pytest.raises(Failed) as excinfo:
            common.load_devlogs("fvv")
        assert "unreadable" in (excinfo.value.msg or "")

    def test_returns_entries_when_ledger_files_exist(
        self, tmp_path, monkeypatch, single_actor_replicas
    ):
        monkeypatch.setattr(common, "_DEVLOGS_DIR", tmp_path)
        actor_dir = tmp_path / "fvv" / "case-actor"
        actor_dir.mkdir(parents=True)
        (tmp_path / "fvv" / DUMP_MANIFEST_FILENAME).write_text(
            json.dumps({"demoName": "fvv", "ledgerFileCount": 1}),
            encoding="utf-8",
        )
        entries = single_actor_replicas["case-actor"]
        (actor_dir / "test-case-case-ledger.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8"
        )

        replicas = common.load_devlogs("fvv")

        assert list(replicas) == ["case-actor"]
        assert [common.log_index(e) for e in replicas["case-actor"]] == list(
            range(len(entries))
        )

    def test_skip_survives_when_no_demo_name_and_no_manifest(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(common, "_DEVLOGS_DIR", tmp_path)
        (tmp_path / "unrelated").mkdir()
        with pytest.raises(Skipped) as excinfo:
            common.load_devlogs()
        assert "devlogs/" in str(excinfo.value)

    def test_filters_entries_by_manifest_case_id_on_accumulation(
        self, tmp_path, monkeypatch
    ):
        """load_devlogs filters out entries from prior runs via manifest caseId.

        When devlogs/ accumulates ledger files from multiple runs, the
        hash-chain invariant fails because entries from different cases are
        concatenated into one log.  The manifest's caseId identifies the
        current run; load_devlogs must drop any entry whose caseId differs.
        Regression: issue #2273.
        """
        monkeypatch.setattr(common, "_DEVLOGS_DIR", tmp_path)
        actor_dir = tmp_path / "fv" / "case-actor"
        actor_dir.mkdir(parents=True)

        CASE_A = "https://example.org/cases/case-a"
        CASE_B = "https://example.org/cases/case-b"

        entry_a = {
            "logIndex": 0,
            "entryHash": "ha",
            "prevLogHash": "0",
            "event_type": "old_event",
            "caseId": CASE_A,
        }
        entry_b = {
            "logIndex": 0,
            "entryHash": "hb",
            "prevLogHash": "0",
            "event_type": "new_event",
            "caseId": CASE_B,
        }

        # Two JSONL files — one from each run — simulating local accumulation
        (actor_dir / "case-a-case-ledger.jsonl").write_text(
            json.dumps(entry_a) + "\n", encoding="utf-8"
        )
        (actor_dir / "case-b-case-ledger.jsonl").write_text(
            json.dumps(entry_b) + "\n", encoding="utf-8"
        )

        # Manifest identifies the most recent run as case-b
        (tmp_path / "fv" / DUMP_MANIFEST_FILENAME).write_text(
            json.dumps(
                {
                    "demoName": "fv",
                    "caseId": CASE_B,
                    "ledgerFileCount": 1,
                    "targetCount": 1,
                }
            ),
            encoding="utf-8",
        )

        replicas = common.load_devlogs("fv")

        assert "case-actor" in replicas
        case_ids_in_result = {e.get("caseId") for e in replicas["case-actor"]}
        assert case_ids_in_result == {CASE_B}, (
            f"Expected only {CASE_B!r}, got {case_ids_in_result!r}. "
            "load_devlogs must filter by manifest caseId to prevent "
            "hash-chain corruption from cross-run accumulation (issue #2273)."
        )

    def test_fails_when_any_scenario_manifest_reports_no_ledgers(
        self, tmp_path, monkeypatch
    ):
        """Un-scoped loads look for a manifest anywhere beneath devlogs/."""
        monkeypatch.setattr(common, "_DEVLOGS_DIR", tmp_path)
        demo_dir = tmp_path / "fvv"
        demo_dir.mkdir()
        (demo_dir / DUMP_MANIFEST_FILENAME).write_text(
            json.dumps({"demoName": "fvv", "ledgerFileCount": 0}),
            encoding="utf-8",
        )
        with pytest.raises(Failed) as excinfo:
            common.load_devlogs()
        assert "no case-ledger" in (excinfo.value.msg or "").lower()


# ---------------------------------------------------------------------------
# _AllSkipGuard (DEMOCI-10-005)
# ---------------------------------------------------------------------------

import types as _types  # noqa: E402

from test.ci.invariants.conftest import _AllSkipGuard  # noqa: E402


def _rpt(when: str, outcome: str):
    return _types.SimpleNamespace(when=when, outcome=outcome)


def _ses(exitstatus: int = 0):
    return _types.SimpleNamespace(exitstatus=exitstatus)


class TestAllSkipGuard:
    """DEMOCI-10-005: all-skip session must not exit 0."""

    def test_forces_exit_1_on_fixture_level_skips(self):
        """All tests skipped at setup (fixture skip) → exitstatus forced to 1."""
        guard = _AllSkipGuard()
        for _ in range(3):
            guard.pytest_runtest_logreport(_rpt("setup", "skipped"))
        session = _ses(0)
        guard.pytest_sessionfinish(session=session)
        assert session.exitstatus == 1

    def test_forces_exit_1_on_call_level_skips(self):
        """All tests skipped in the test body → exitstatus forced to 1."""
        guard = _AllSkipGuard()
        for _ in range(2):
            guard.pytest_runtest_logreport(_rpt("call", "skipped"))
        session = _ses(0)
        guard.pytest_sessionfinish(session=session)
        assert session.exitstatus == 1

    def test_does_not_trigger_when_any_test_passes(self):
        """One passing test among skips → exitstatus unchanged."""
        guard = _AllSkipGuard()
        guard.pytest_runtest_logreport(_rpt("setup", "skipped"))
        guard.pytest_runtest_logreport(_rpt("call", "passed"))
        session = _ses(0)
        guard.pytest_sessionfinish(session=session)
        assert session.exitstatus == 0

    def test_does_not_trigger_on_empty_session(self):
        """No tests reported → exitstatus unchanged."""
        guard = _AllSkipGuard()
        session = _ses(0)
        guard.pytest_sessionfinish(session=session)
        assert session.exitstatus == 0

    def test_does_not_trigger_when_tests_fail(self):
        """Failed tests → guard does not alter the already-nonzero exitstatus."""
        guard = _AllSkipGuard()
        guard.pytest_runtest_logreport(_rpt("call", "failed"))
        session = _ses(1)
        guard.pytest_sessionfinish(session=session)
        assert session.exitstatus == 1

    def test_ignores_teardown_reports(self):
        """Teardown outcomes are not tracked; a setup skip still triggers."""
        guard = _AllSkipGuard()
        guard.pytest_runtest_logreport(_rpt("teardown", "passed"))
        guard.pytest_runtest_logreport(_rpt("setup", "skipped"))
        session = _ses(0)
        guard.pytest_sessionfinish(session=session)
        assert session.exitstatus == 1

    def test_does_not_trigger_for_xfail_expected_failures(self):
        """xfail expected-failure (outcome='skipped', wasxfail set) → not counted."""
        guard = _AllSkipGuard()
        rpt = _types.SimpleNamespace(
            when="call", outcome="skipped", wasxfail="reason"
        )
        guard.pytest_runtest_logreport(rpt)
        session = _ses(0)
        guard.pytest_sessionfinish(session=session)
        assert session.exitstatus == 0
