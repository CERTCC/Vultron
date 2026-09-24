"""Tests for the shrink-only baseline of upward level dependencies (AC-4, #3529).

Requirements: DF-11-002; a stale entry is attributed per MS-17-001.
"""

from __future__ import annotations

import pytest

from test.metadata.docs._level_tree import (
    VIOLATING,
    failures,
    make_repo,
    leveled_page,
)
from vultron.metadata.docs import level_order
from vultron.metadata.docs.level_order import (
    check_level_order,
    prune_baseline,
    read_baseline,
    write_baseline,
)
from vultron.metadata.file_loading import MetadataLoadErrors

# ---------------------------------------------------------------------------
# Baseline (AC-4)
# ---------------------------------------------------------------------------

#: The committed baseline, pinned. It may only shrink: drop a key here when
#: ``--prune-baseline`` drops it from the file, and never add one. Pinning the
#: keys rather than their count also stops an entry being swapped for another
#: (AC-4 of #3529).
_BASELINED = frozenset(
    {
        ("howto/activitypub/activities/error.md", "CASE_MANAGER"),
        ("howto/activitypub/activities/initialize_case.md", "CASE_MANAGER"),
        ("howto/activitypub/activities/invite_actor.md", "CASE_MANAGER"),
        ("howto/activitypub/activities/invite_actor.md", "Embargo Consent"),
        ("howto/activitypub/activities/manage_case.md", "CASE_MANAGER"),
        (
            "howto/activitypub/activities/manage_participants.md",
            "CASE_MANAGER",
        ),
        (
            "howto/activitypub/activities/role_delegation.md",
            "Case Ownership Transfer",
        ),
        ("howto/activitypub/activities/status_updates.md", "CASE_MANAGER"),
        ("howto/activitypub/activities/suggest_actor.md", "CASE_MANAGER"),
        ("ns/index.md", "Embargo Consent"),
        ("reference/activitypub/objects.md", "CaseParticipant"),
        ("reference/fv-demo-protocol.md", "CASE_MANAGER"),
        ("reference/fv-demo-protocol.md", "Case Ledger Entry"),
        ("reference/fv-demo-protocol.md", "VulnerabilityCase"),
        ("reference/vultron-taxonomy.md", "CASE_MANAGER"),
        ("topics/case_lifecycle/index.md", "CASE_MANAGER"),
        (
            "topics/process_models/index.md",
            "Deterministic Finite Automaton (DFA)",
        ),
        ("topics/process_models/model_interactions/index.md", "CASE_MANAGER"),
        ("topics/process_models/model_interactions/index.md", "Global State"),
        ("topics/scenarios/fccv-handoff.md", "Case Ownership Transfer"),
        ("topics/scenarios/fcv.md", "Case Ledger Entry"),
        ("topics/scenarios/fvcv-handoff.md", "Case Ledger Entry"),
        ("topics/scenarios/fvcv-handoff.md", "Case Ownership Transfer"),
        ("topics/scenarios/index.md", "Case Ledger Entry"),
        ("tutorials/container_demos.md", "Case Ownership Transfer"),
        ("tutorials/other_demos.md", "Case Ownership Transfer"),
    }
)


@pytest.mark.spec("DF-11-002")
class TestBaseline:
    def test_baselined_violation_is_tolerated(self, tmp_path):
        root = make_repo(tmp_path, {"howto/a.md": VIOLATING})
        key = ("howto/a.md", "Case Ledger Entry")

        result = check_level_order(root, baseline={key: "awaiting #1"})

        assert result.baselined == [key]

    def test_stale_committed_entry_names_its_line(self, tmp_path, monkeypatch):
        root = make_repo(tmp_path, {"howto/a.md": leveled_page(300)})
        path = tmp_path / "baseline.txt"
        write_baseline({("howto/a.md", "Case Ledger Entry"): "old"}, path)
        monkeypatch.setattr(level_order, "BASELINE_PATH", path)

        with pytest.raises(MetadataLoadErrors) as info:
            check_level_order(root)

        (failure,) = info.value.failures
        entry_line = (
            path.read_text()
            .splitlines()
            .index("howto/a.md | Case Ledger Entry | old")
        )
        assert failure.location == f"baseline.txt:{entry_line + 1}"

    def test_stale_entry_fails(self, tmp_path):
        root = make_repo(tmp_path, {"howto/a.md": leveled_page(300)})

        (failure,) = failures(
            root, baseline={("howto/a.md", "Case Ledger Entry"): "old"}
        )

        assert "no longer a violation" in failure.detail
        assert "--prune-baseline" in failure.detail
        assert "_BASELINED" in failure.detail

    @pytest.mark.parametrize(
        "line",
        [
            "howto/a.md | Case Ledger Entry",
            "howto/a.md | Case Ledger Entry | ",
        ],
        ids=["two-fields", "empty-reason"],
    )
    def test_entry_without_a_reason_is_malformed(self, tmp_path, line):
        path = tmp_path / "baseline.txt"
        path.write_text(f"# header\n\n{line}\n")

        with pytest.raises(MetadataLoadErrors) as info:
            read_baseline(path)

        (failure,) = info.value.failures
        assert failure.location == "baseline.txt:3"
        assert "names why it is unfixed" in failure.detail

    def test_repeated_entry_is_malformed(self, tmp_path):
        path = tmp_path / "baseline.txt"
        path.write_text("a.md | T | r\na.md | T | r2\n")

        with pytest.raises(MetadataLoadErrors, match="repeats"):
            read_baseline(path)

    def test_round_trip(self, tmp_path):
        path = tmp_path / "baseline.txt"
        entries = {("b.md", "T"): "why b", ("a.md", "T"): "why a"}

        write_baseline(entries, path)

        assert read_baseline(path) == entries
        body = [
            ln
            for ln in path.read_text().splitlines()
            if ln and not ln.startswith("#")
        ]
        assert body == ["a.md | T | why a", "b.md | T | why b"]

    def test_prune_only_removes(self, tmp_path):
        root = make_repo(tmp_path, {"howto/a.md": VIOLATING})
        path = tmp_path / "baseline.txt"
        write_baseline(
            {
                ("howto/a.md", "Case Ledger Entry"): "still open",
                ("howto/gone.md", "Case Ledger Entry"): "fixed",
            },
            path,
        )

        removed = prune_baseline(root, baseline_path=path)

        assert removed == 1
        assert read_baseline(path) == {
            ("howto/a.md", "Case Ledger Entry"): "still open"
        }

    def test_prune_keeps_an_entry_for_an_unreadable_page(self, tmp_path):
        """A page that fails to load has unknown violations, not none."""
        root = make_repo(
            tmp_path,
            {
                "howto/a.md": VIOLATING,
                "howto/b.md": "---\nlevel: [\n---\nx\n",
            },
        )
        path = tmp_path / "baseline.txt"
        entries = {
            ("howto/a.md", "Case Ledger Entry"): "open",
            ("howto/b.md", "Case Ledger Entry"): "unreadable",
        }
        write_baseline(entries, path)

        assert prune_baseline(root, baseline_path=path) == 0
        assert read_baseline(path) == entries

    def test_committed_baseline_never_grows(self):
        """When the baseline is pruned, drop the key here; never add one."""
        added = set(read_baseline()) - _BASELINED
        assert not added, (
            f"level_order_baseline.txt gained {sorted(added)}. Link each new "
            f"use to its introducing page (SG-11) instead of baselining it."
        )

    def test_pin_matches_the_committed_baseline(self):
        """A pruned entry leaves the pin too, so the pin cannot re-admit it."""
        assert _BASELINED == set(read_baseline())
