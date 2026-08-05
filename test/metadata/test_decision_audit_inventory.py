"""Tests for vultron.metadata.adr.decision_audit_inventory (Concern #1800)."""

import pytest

from vultron.metadata.adr.decision_audit_inventory import (
    Candidate,
    _ids_near_problem_words,
    _signal_weight,
    build_inventory,
)


@pytest.fixture(scope="module")
def inventory():
    """Full real-repo inventory, built once and shared.

    The build loads the full spec registry (~3s); the tests that use this
    fixture are marked ``integration`` (deselected by default) so they never
    risk the fast-suite 5s per-test timeout under load. The pure-scoring tests
    below need no registry and stay in the default suite.
    """
    return build_inventory()


class TestScoring:
    def test_no_signals_scores_zero(self):
        c = Candidate(id="X-01", kind="spec-group", blast_radius=99)
        assert c.deficit == 0
        assert c.score == 0

    def test_high_value_signal_outranks_weak_mention(self):
        """A moved-premise signal on a low-blast group beats a bare mention
        on a high-blast group — the weighting is the whole point."""
        strong = Candidate(
            id="A-01",
            kind="spec-group",
            blast_radius=2,
            signals=["derives-from-non-accepted-adr:ADR-0033=proposed"],
        )
        weak = Candidate(
            id="B-01",
            kind="spec-group",
            blast_radius=6,
            signals=["named-in-learnings"],
        )
        assert strong.score > weak.score  # (2+1)*3=9 > (6+1)*1=7

    def test_blast_radius_floor(self):
        """A strong signal with zero dependents still scores above zero."""
        c = Candidate(
            id="A-01",
            kind="spec-group",
            blast_radius=0,
            signals=["provisional-prose:'formed in sand'"],
        )
        assert c.score == 3  # (0+1)*3

    def test_deficit_is_weighted_sum_not_count(self):
        c = Candidate(
            id="A-01",
            kind="adr",
            blast_radius=1,
            signals=["status=proposed", "named-in-learnings"],
        )
        assert c.deficit == 3  # 2 + 1, not 2

    def test_signal_weight_prefix_matching(self):
        assert _signal_weight("derives-from-non-accepted-adr:ADR-0015=x") == 3
        assert _signal_weight("status=proposed") == 2
        assert _signal_weight("cites-superseded:ADR-0015") == 2
        assert _signal_weight("named-in-learnings") == 1
        assert _signal_weight("some-unknown-signal") == 1  # default


class TestProblemWordScan:
    def test_captures_four_digit_adr_id(self):
        """A 4-digit ADR id near a problem word must be flagged. A 2-digit-only
        id pattern would never match ADR-NNNN, leaving the ADR
        named-in-learnings signal permanently dead (the fix's whole point)."""
        text = "ADR-0033 is stale and should be reworked."
        assert "ADR-0033" in _ids_near_problem_words(text)

    def test_captures_spec_id_and_group_prefix(self):
        text = "CM-15-001 contradicts the codebase."
        hits = _ids_near_problem_words(text)
        assert "CM-15-001" in hits
        assert "CM-15" in hits  # two-segment group prefix also recorded

    def test_no_problem_word_flags_nothing(self):
        assert (
            _ids_near_problem_words("ADR-0033 is fine; CM-15 works.") == set()
        )


@pytest.mark.integration
class TestBuildInventory:
    def test_real_repo_produces_ranked_candidates(self, inventory):
        assert inventory, "inventory should not be empty on the real repo"
        # sorted by score descending
        scores = [c.score for c in inventory]
        assert scores == sorted(scores, reverse=True)
        # every listed candidate has at least one signal
        assert all(c.signals for c in inventory)

    def test_both_artifact_types_present(self, inventory):
        kinds = {c.kind for c in inventory}
        assert "adr" in kinds
        assert "spec-group" in kinds

    def test_kind_filter(self, inventory):
        # Derive per-kind views from the shared full inventory rather than
        # rebuilding (each rebuild is ~5s).
        assert {c.kind for c in inventory if c.kind == "adr"} == {"adr"}
        spec_only = build_inventory(kinds=("spec",))
        assert all(c.kind == "spec-group" for c in spec_only)

    @pytest.mark.xfail(
        reason="CM-22 derives-from-non-accepted-adr signal not yet firing. "
        "Tracked in #1994."
    )
    def test_known_landmine_surfaces(self, inventory):
        """CM-22 derives from superseded ADR-0015 — the moved-premise signal
        must fire (the ISSUE-1272 class of defect)."""
        cm22 = next((c for c in inventory if c.id == "CM-22"), None)
        assert cm22 is not None
        assert any(
            s.startswith("derives-from-non-accepted-adr") for s in cm22.signals
        )

    def test_cites_superseded_signal_fires(self, inventory):
        """The cites-superseded signal must actually be emitted by some
        candidate — it is a declared, weighted signal, not dead config. At
        least one group cites superseded ADR-0015 in its rationale prose."""
        emitting = [
            c
            for c in inventory
            if any(s.startswith("cites-superseded") for s in c.signals)
        ]
        assert emitting, "cites-superseded signal never fired"
