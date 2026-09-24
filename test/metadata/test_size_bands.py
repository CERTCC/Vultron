"""Tests for vultron.metadata.planning.size_bands.

Pure: no network, no git, no filesystem except the one CLI test that measures a
real diff, which is skipped when ``origin/main`` is not fetched.

The point of most of these is not that 100 and 400 and 1200 are the right
numbers — they are a review-budget policy and the module docstring argues for
them. The point is that the numbers exist *once*, so the tests pin the
**derivation** (weights come from the table, floors come from the ceiling above
them, the top band has no weight) rather than re-typing the table and creating
the ninth copy of it.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from vultron.metadata.planning.size_bands import (
    LABEL_COLORS,
    SIZE_BANDS,
    SIZE_LABELS,
    SIZE_WEIGHTS,
    UNBUNDLABLE_LABELS,
    UNSIZED_WEIGHT,
    _diff_lines,
    band_for_acs,
    band_for_diff,
    main,
    markdown_table,
    weight_of,
)


class TestTableShape:
    """Invariants the derived constants rely on."""

    def test_bands_are_ordered_smallest_first(self):
        ceilings = [b.max_lines for b in SIZE_BANDS if b.max_lines is not None]
        assert ceilings == sorted(ceilings)

    def test_exactly_one_band_is_unbounded_and_it_is_last(self):
        unbounded = [b for b in SIZE_BANDS if b.max_lines is None]
        assert unbounded == [SIZE_BANDS[-1]]

    def test_the_estimate_domain_is_unbounded_only_at_its_end(self):
        """`band_for_acs` relies on this, and only ``max_lines`` was checked.

        Give ``size:L`` a finite ``max_acs`` and the loop falls through to a
        ``# pragma: no cover`` ``AssertionError`` for every count above it,
        which coverage cannot flag — and the parametrized boundary test starts
        silently comparing against the ``measured_only`` band instead.
        """
        estimable = [b for b in SIZE_BANDS if not b.measured_only]
        unbounded = [b for b in estimable if b.max_acs is None]
        assert unbounded == [estimable[-1]]

    def test_every_band_has_a_colour(self):
        assert set(LABEL_COLORS) == set(SIZE_LABELS)

    def test_labels_are_unique(self):
        assert len(set(SIZE_LABELS)) == len(SIZE_LABELS)


class TestCalibratedValues:
    """The one place a literal belongs: the table is the authority.

    Every other test here reads its threshold out of ``SIZE_BANDS``, which pins
    the *derivation* but cannot fail on a wrong number — change ``max_lines`` to
    1000 and the rest of this file stays green while PAD-05-008 and PAD-05-009
    are both violated. Seven spec requirements state these numbers normatively
    and name this file as their verification, so the numbers are asserted here
    once, against the spec, and nowhere else.
    """

    def test_the_line_thresholds_are_the_surveyed_ones(self):
        # PAD-05-006/007/008/009: ≤100 / 101-400 / 401-1200 / 1201+.
        assert [b.max_lines for b in SIZE_BANDS] == [100, 400, 1200, None]

    def test_the_ac_thresholds_are_the_surveyed_ones(self):
        # PAD-05-001/004/005: ≤2 / 3-6 / 7+, and XL is unreachable (PAD-05-012).
        assert [b.max_acs for b in SIZE_BANDS] == [2, 6, None, None]

    def test_the_bundle_weights_are_one_two_three_then_never(self):
        # PAD-15-005/PAD-15-011. `size:M` = 2 is pinned nowhere else: the
        # budget tests reach 1 and 3 indirectly, so dropping M to 1 would let
        # five M-sized members into a budget-6 bundle with the suite green.
        assert [b.weight for b in SIZE_BANDS] == [1, 2, 3, None]

    def test_the_labels_are_s_m_l_xl_in_that_order(self):
        assert SIZE_LABELS == ("size:S", "size:M", "size:L", "size:XL")


class TestDerivation:
    """Nothing below may be written down twice."""

    def test_weights_derive_from_the_band_table(self):
        assert SIZE_WEIGHTS == {
            b.label: b.weight for b in SIZE_BANDS if b.weight is not None
        }

    def test_unbundlable_labels_are_exactly_the_weightless_bands(self):
        assert UNBUNDLABLE_LABELS == {
            b.label for b in SIZE_BANDS if b.weight is None
        }

    def test_unsized_weight_is_the_largest_bundlable_weight(self):
        """Not the largest band. `size:` is on 91% of open Tasks, so treating
        the unlabelled 9% as unbundlable would fail closed, not safe."""
        assert UNSIZED_WEIGHT == max(SIZE_WEIGHTS.values())
        heaviest = max(SIZE_WEIGHTS, key=lambda label: SIZE_WEIGHTS[label])
        assert heaviest not in UNBUNDLABLE_LABELS

    def test_a_bands_floor_is_one_past_the_previous_ceiling(self):
        for previous, band in zip(SIZE_BANDS, SIZE_BANDS[1:]):
            ceiling = previous.max_lines
            assert ceiling is not None, "only the last band is unbounded"
            assert band.lines_range.startswith(f"{ceiling + 1}")

    def test_the_first_band_renders_as_a_ceiling_only(self):
        assert SIZE_BANDS[0].lines_range == f"≤{SIZE_BANDS[0].max_lines}"

    def test_the_last_band_renders_as_open_ended(self):
        assert SIZE_BANDS[-1].lines_range.endswith("+")


class TestBandForDiff:
    """Classification is inclusive at every ceiling."""

    @pytest.mark.parametrize("band", SIZE_BANDS)
    def test_each_ceiling_and_the_line_after_it_land_correctly(self, band):
        if band.max_lines is None:
            pytest.skip("unbounded band has no ceiling to probe")
        index = SIZE_BANDS.index(band)
        assert band_for_diff(band.max_lines) is band
        assert band_for_diff(band.max_lines + 1) is SIZE_BANDS[index + 1]

    def test_an_empty_diff_is_the_smallest_band(self):
        assert band_for_diff(0) is SIZE_BANDS[0]

    def test_an_enormous_diff_is_the_largest_band(self):
        # The largest PR in the survey window: 28,576 lines.
        assert band_for_diff(28_576) is SIZE_BANDS[-1]

    def test_a_negative_diff_is_rejected_by_name(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            band_for_diff(-1)


class TestBandForAcs:
    """The estimate domain, which the top band is deliberately outside of."""

    @pytest.mark.parametrize("band", SIZE_BANDS)
    def test_each_ceiling_and_the_one_after_it_land_correctly(self, band):
        if band.measured_only or band.max_acs is None:
            pytest.skip("no AC ceiling to probe")
        index = SIZE_BANDS.index(band)
        assert band_for_acs(band.max_acs) is band
        assert band_for_acs(band.max_acs + 1) is SIZE_BANDS[index + 1]

    def test_no_ac_count_can_reach_a_measured_only_band(self):
        """An Issue predicted that large should be decomposed, not labelled XL.
        XL is reachable only by measuring a PR that already grew too big."""
        for count in (0, 1, 7, 50, 10_000):
            assert not band_for_acs(count).measured_only

    def test_a_negative_ac_count_is_rejected_by_name(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            band_for_acs(-1)

    def test_the_ac_range_of_a_measured_only_band_is_blank(self):
        assert SIZE_BANDS[-1].acs_range == "—"


class TestWeightOf:
    """PAD-15-005, shared with `bundle_fit.Candidate.weight`."""

    def test_the_largest_label_wins(self):
        assert weight_of(["size:S", "size:L"]) == SIZE_WEIGHTS["size:L"]

    def test_no_label_counts_as_the_largest_bundlable_size(self):
        assert weight_of([]) == UNSIZED_WEIGHT
        assert weight_of(["specs-notes"]) == UNSIZED_WEIGHT

    def test_an_unbundlable_label_alone_does_not_read_as_small(self):
        """It has no weight, so the fallback applies — and `select` refuses the
        candidate before anything reads the number."""
        only_xl = sorted(UNBUNDLABLE_LABELS)[:1]
        assert weight_of(only_xl) == UNSIZED_WEIGHT


class TestDescriptions:
    """The GitHub label UI is a ninth copy unless it is generated."""

    def test_every_description_names_its_own_range(self):
        for band in SIZE_BANDS:
            assert band.lines_range in band.description

    def test_the_measured_only_band_says_why_it_exists(self):
        assert "review quality degrades" in SIZE_BANDS[-1].description

    def test_the_table_has_one_row_per_band(self):
        rows = markdown_table().splitlines()
        assert len(rows) == len(SIZE_BANDS) + 2  # header + delimiter
        for band in SIZE_BANDS:
            assert any(f"`{band.label}`" in row for row in rows)


class TestCLI:
    """Error messages are the product (vultron/metadata/AGENTS.md)."""

    def test_lines_reports_the_band_and_the_measurement(self, capsys):
        assert main(["--lines", "700"]) == 0
        out = capsys.readouterr().out
        assert "size:L" in out and "700 diff lines" in out

    def test_quiet_prints_only_the_label_for_shell_capture(self, capsys):
        assert main(["--lines", "42", "--quiet"]) == 0
        assert capsys.readouterr().out.strip() == "size:S"

    def test_acs_reports_the_estimate(self, capsys):
        assert main(["--acs", "4"]) == 0
        out = capsys.readouterr().out
        assert "size:M" in out and "estimate" in out

    def test_an_oversized_diff_explains_itself(self, capsys):
        assert main(["--lines", "5000"]) == 0
        out = capsys.readouterr().out
        assert "size:XL" in out
        assert "Split it" in out or "split" in out.lower()

    def test_negative_input_exits_2_with_a_message(self, capsys):
        assert main(["--lines", "-5"]) == 2
        assert "cannot be negative" in capsys.readouterr().err

    def test_an_unknown_base_ref_names_the_ref(self, capsys):
        assert main(["--base", "no/such/ref"]) == 2
        err = capsys.readouterr().err
        assert "no/such/ref" in err

    def test_lines_and_acs_are_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            main(["--lines", "10", "--acs", "3"])

    def test_table_prints_markdown(self, capsys):
        assert main(["--table"]) == 0
        assert capsys.readouterr().out.startswith("| Label |")

    def test_labels_json_is_loadable_and_covers_every_band(self, capsys):
        assert main(["--labels-json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert [row["name"] for row in payload] == list(SIZE_LABELS)
        assert all(row["description"] and row["color"] for row in payload)

    def test_base_measures_a_real_diff(self, capsys):
        """Against this repo. Skipped in a clone without the remote ref."""
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", "origin/main"],
            capture_output=True,
            text=True,
        )
        if probe.returncode != 0:
            pytest.skip("origin/main not available in this clone")
        assert main(["--base", "origin/main", "--quiet"]) == 0
        assert capsys.readouterr().out.strip() in SIZE_LABELS


def _init_repo(path):
    """A throwaway repo with one commit on ``main``."""

    def git(*args):
        subprocess.run(
            ["git", "-C", str(path), *args], check=True, capture_output=True
        )

    (path / "pyproject.toml").write_text("[project]\nname='probe'\n")
    git("init", "-q", "-b", "main")
    git("config", "user.email", "probe@example.invalid")
    git("config", "user.name", "probe")
    git("add", "-A")
    git("-c", "commit.gpgsign=false", "commit", "-qm", "base")
    return git


class TestDiffMeasurement:
    """What counts as "this branch's diff" — the part that measured 0.

    `_diff_lines` compares the merge base to the **working tree**, because an
    agent asks for the size before the commit exists. The `base...HEAD` form
    answered 0 for a branch with 800 uncommitted lines in it, and a sizing tool
    that is confidently wrong is worse than no tool.
    """

    @pytest.fixture
    def probe(self, tmp_path, monkeypatch):
        git = _init_repo(tmp_path)
        monkeypatch.setattr(
            "vultron.metadata.planning.size_bands.repo_root",
            lambda *a, **k: tmp_path,
        )
        return tmp_path, git

    def test_uncommitted_edits_to_a_tracked_file_count(self, probe):
        root, _git = probe
        (root / "pyproject.toml").write_text(
            "[project]\nname='probe'\n" + "# pad\n" * 40
        )
        assert _diff_lines("main") == 40

    def test_an_untracked_new_file_counts(self, probe):
        """The shape of most agent work: the change is a file git cannot see
        yet, so `git diff` alone reports nothing at all."""
        root, _git = probe
        (root / "new_module.py").write_text("x = 1\n" * 120)
        assert _diff_lines("main") == 120

    def test_committed_and_uncommitted_work_are_summed(self, probe):
        """On a branch, as real work is — committing to `main` itself would
        move the merge base and hide the committed half."""
        root, git = probe
        git("checkout", "-q", "-b", "task/1-probe")
        (root / "committed.py").write_text("a = 1\n" * 10)
        git("add", "-A")
        git("-c", "commit.gpgsign=false", "commit", "-qm", "work")
        (root / "pending.py").write_text("b = 2\n" * 7)
        assert _diff_lines("main") == 17

    def test_a_clean_branch_measures_zero(self, probe):
        assert _diff_lines("main") == 0

    def test_a_gitignored_file_is_not_counted(self, probe):
        root, git = probe
        (root / ".gitignore").write_text("junk/\n")
        git("add", "-A")
        git("-c", "commit.gpgsign=false", "commit", "-qm", "ignore")
        (root / "junk").mkdir()
        (root / "junk" / "cache.txt").write_text("noise\n" * 500)
        assert _diff_lines("main") == 0

    def test_an_untracked_binary_file_contributes_nothing(self, probe):
        """Matching --numstat, which reports "-" for binary files."""
        root, _git = probe
        (root / "blob.bin").write_bytes(b"\x00\x01\x02" * 100)
        assert _diff_lines("main") == 0

    def test_a_file_with_no_trailing_newline_counts_its_last_line(self, probe):
        root, _git = probe
        (root / "terse.py").write_text("one\ntwo")
        assert _diff_lines("main") == 2
