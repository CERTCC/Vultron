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

"""Shape, drift and mutation tests for the plot manifest (DEMOCI-11-034).

``vultron/demo/scenario/plots.json`` lists every registered scenario's
flattened story: each ``choose(...)`` by branch point, choice and deciding
cast member, and each fragment by qualified name, in the order the story
plays them.  :mod:`vultron.metadata.demo_scenarios.sync` drift-checks it with
the other registry artifacts (DEMOCI-11-005, DEMOCI-11-035).

Three questions are asked here, and they fail for different reasons:

* **The committed manifest is the stories in the code**
  (``test_the_committed_manifest_matches_a_fresh_export``) — the drift
  assertion, which names the regeneration command.
* **The check is not vacuous**
  (``test_moving_a_choose_past_its_fragment_fails_the_check``) — the one
  mutation the manifest exists for.  ``TestSharedPrefixes`` cannot see it,
  because it compares two committed recordings with each other and a
  reordered shared fragment moves both alike.
* **The projection is the shape the spec names** (``TestManifestShape``) —
  one entry per registered scenario, its items in story order, and a refusal
  rather than an unstable entry.  The naming rule that refusal rests on is
  pinned beside the function that owns it, in
  ``test/demo_unit/story/test_assembly.py``.

To fix a drift failure here::

    uv run demo-scenarios --write
    git add vultron/demo/scenario/plots.json
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from test.support.scenario_specs import fixture_spec
from vultron.demo.helpers.story import (
    Choose,
    Story,
    StoryState,
    choose,
    story,
)
from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios
from vultron.errors import DemoStoryError
from vultron.metadata.demo_scenarios import sync
from vultron.metadata.demo_scenarios.plots import (
    CHOICE_KIND,
    FRAGMENT_KIND,
    PLOT_MANIFEST,
    plot_manifest,
    plot_rows,
)
from vultron.metadata.demo_scenarios.sync import (
    ARTIFACTS,
    WRITE_COMMAND,
    stale_artifacts,
    write_artifacts,
)
from vultron.metadata.generated_files import read_committed

_REPO_ROOT = Path(__file__).parents[3]

#: The fixture scenario's name. Never registered: every test that uses it
#: passes its spec explicitly, so the real registry is untouched.
_FIXTURE_NAME = "zz-plot"

#: The fixture's one decision, a real branch-point table entry so ``choose``
#: validates it as a scenario's own would.
_BRANCH_POINT = "reporter-whom-to-tell"
_CHOICE = "vendor"
_DECIDED_BY = "reporter"


def reporter_submits_the_report(state: StoryState) -> None:
    """Stand in for a story fragment; the manifest only reads its name."""


def _ordered_story() -> Story:
    """The fixture story as written: the decision, then the step it decides."""
    return story(
        choose(_BRANCH_POINT, _CHOICE, by=_DECIDED_BY),
        reporter_submits_the_report,
    )


def _reordered_story() -> Story:
    """The same two items with the ``choose`` moved past its fragment.

    The mutation of PR #5588 (#5589): the story still walks the same path and
    still plays the same fragment, so every other generated artifact, the
    step-report ratchet and ``TestComposedFamilies`` stay green.
    """
    return story(
        reporter_submits_the_report,
        choose(_BRANCH_POINT, _CHOICE, by=_DECIDED_BY),
    )


def _fixture_spec(plot: Story) -> ScenarioSpec:
    """A spec carrying *plot* as its story."""
    return fixture_spec(name=_FIXTURE_NAME, label="ZZ-plot", story=plot)


def _committed_scenarios() -> dict[str, list[dict[str, str]]]:
    """Return the committed manifest's ``scenarios`` map.

    Reads the artifact once and fails naming it when it is absent or empty,
    rather than letting ``json.loads(... or "{}")`` turn a missing file into
    a ``KeyError`` on ``scenarios`` — the "falls back to" shape
    ``notes/testing-pitfalls.md`` warns about.
    """
    text = read_committed(_REPO_ROOT / PLOT_MANIFEST)
    assert text, (
        f"{PLOT_MANIFEST} is missing or empty. Run '{WRITE_COMMAND}' and "
        f"commit it (DEMOCI-11-034)."
    )
    payload = json.loads(text)
    assert "scenarios" in payload, (
        f"{PLOT_MANIFEST} holds no 'scenarios' key, so it is not a plot "
        f"manifest. Run '{WRITE_COMMAND}' and commit it (DEMOCI-11-034)."
    )
    scenarios = payload["scenarios"]
    assert isinstance(scenarios, dict), type(scenarios).__name__
    return scenarios


_CHOICE_ROW = {
    "kind": CHOICE_KIND,
    "branch_point": _BRANCH_POINT,
    "choice": _CHOICE,
    "by": _DECIDED_BY,
}
_FRAGMENT_ROW = {
    "kind": FRAGMENT_KIND,
    "name": f"{__name__}.reporter_submits_the_report",
}


# ---------------------------------------------------------------------------
# Drift (DEMOCI-11-035)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOCI-11-034", "DEMOCI-11-035")
def test_the_committed_manifest_matches_a_fresh_export() -> None:
    """The committed manifest is what the registry's stories render today."""
    assert PLOT_MANIFEST not in stale_artifacts(_REPO_ROOT), (
        f"{PLOT_MANIFEST} is stale: a story's items changed and the manifest "
        f"was not regenerated. Run '{WRITE_COMMAND}' and commit "
        f"{PLOT_MANIFEST} (DEMOCI-11-035)."
    )


@pytest.fixture
def fixture_root(tmp_path: Path) -> Path:
    """A tree whose artifacts are generated from the fixture scenario alone.

    The two markdown artifacts are spliced into hand-written prose that
    cannot be regenerated, so they are copied from the repository first; the
    whole-file artifacts are then written from the one fixture spec. Starting
    from a one-scenario registry is what isolates the mutation below: nothing
    else in the tree can be the reason an artifact is reported stale.
    """
    for artifact in ARTIFACTS:
        if artifact.whole_file:
            continue
        target = tmp_path / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_REPO_ROOT / artifact.path, target)
    write_artifacts(tmp_path, (_fixture_spec(_ordered_story()),))
    return tmp_path


@pytest.mark.spec("DEMOCI-11-035")
def test_moving_a_choose_past_its_fragment_fails_the_check(
    fixture_root: Path,
) -> None:
    """The reorder the manifest exists for is reported, and only by it.

    Both halves matter. The manifest is stale, so the gate is not vacuous;
    and no *other* artifact is, which is why a reorder needed a new artifact
    rather than a stricter reading of an existing one — the CI matrix and the
    two scenario tables are projections of the decorator's prose fields, and
    the path is unchanged.
    """
    assert (
        stale_artifacts(fixture_root, (_fixture_spec(_ordered_story()),)) == []
    )

    stale = stale_artifacts(fixture_root, (_fixture_spec(_reordered_story()),))

    assert stale == [PLOT_MANIFEST]


@pytest.mark.spec("DEMOCI-11-035")
def test_check_names_the_regeneration_command(
    fixture_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--check`` exits 1 and tells the reader which command rewrites it.

    Two of ``--check``'s other findings are stubbed out, and both would
    otherwise change the answer rather than add to it. The prose consistency
    checks are the other half of ADR-0098's split and have their own tests;
    in a one-scenario tree they would report every real page and table as a
    disagreement. The derived-path check would fire on the fixture
    scenario's absent demo module and harness, and ``--check`` then
    deliberately *stops* naming ``--write`` — it cannot make progress until
    the path is fixed — which is the behaviour this test would otherwise be
    asserting the absence of.
    """
    specs = (_fixture_spec(_reordered_story()),)
    monkeypatch.setattr(sync, "repo_root", lambda: fixture_root)
    monkeypatch.setattr(sync, "discover_scenarios", lambda: specs)
    monkeypatch.setattr(sync, "consistency_problems", lambda *_args: [])
    monkeypatch.setattr(sync, "missing_derived_paths", lambda *_args: [])

    with pytest.raises(SystemExit) as raised:
        sync.main(["--check"])

    assert raised.value.code == 1
    reported = capsys.readouterr().err
    assert PLOT_MANIFEST in reported
    assert WRITE_COMMAND in reported


# ---------------------------------------------------------------------------
# Shape (DEMOCI-11-034)
# ---------------------------------------------------------------------------


class TestManifestShape:
    @pytest.mark.spec("DEMOCI-11-034")
    def test_an_entry_lists_the_storys_items_in_order(self) -> None:
        """A choice renders as three names; a fragment as its qualified name."""
        assert plot_rows(_FIXTURE_NAME, _ordered_story()) == [
            _CHOICE_ROW,
            _FRAGMENT_ROW,
        ]

    @pytest.mark.spec("DEMOCI-11-034")
    def test_the_order_is_the_storys_order(self) -> None:
        """Reordering the two items reorders the rows, and nothing else."""
        assert plot_rows(_FIXTURE_NAME, _reordered_story()) == [
            _FRAGMENT_ROW,
            _CHOICE_ROW,
        ]

    @pytest.mark.spec("DEMOCI-11-034")
    def test_every_registered_scenario_has_one_entry(self) -> None:
        """The manifest covers the whole registry, keyed by scenario name.

        ``@scenario`` requires ``story=`` — ``test_a_scenario_cannot_register_
        without_a_story`` in ``test/demo_unit/story/test_assembly.py`` pins
        that — so no registered scenario can be missing from the manifest.
        """
        specs = discover_scenarios()

        assert set(_committed_scenarios()) == {spec.name for spec in specs}

    @pytest.mark.spec("DEMOCI-11-034")
    def test_each_committed_entry_is_its_scenarios_story(self) -> None:
        """Per scenario, the committed rows are that story's items in order.

        The drift assertion above compares the whole file as text, which
        names no scenario when it fails. This one fails on the scenario whose
        story moved, which is what a reader of a red run needs.
        """
        committed = _committed_scenarios()

        for spec in discover_scenarios():
            assert committed[spec.name] == plot_rows(spec.name, spec.story), (
                spec.name
            )

    @pytest.mark.spec("DEMOCI-11-019", "DEMOCI-11-034")
    def test_each_entrys_choices_are_the_scenarios_path(self) -> None:
        """The manifest's choices and the registered path are one fact.

        Both come from the story, so this is the assertion that would catch a
        future change reading one of them from somewhere else.
        """
        for spec in discover_scenarios():
            rows = plot_rows(spec.name, spec.story)
            chosen = tuple(
                (row["branch_point"], row["choice"])
                for row in rows
                if row["kind"] == CHOICE_KIND
            )
            assert chosen == spec.path, spec.name

    @pytest.mark.spec("DEMOCI-11-024", "DEMOCI-11-034")
    def test_a_spec_cannot_be_built_without_a_story(self) -> None:
        """There is no story-less spec for the manifest to leave out.

        A scenario joins the manifest by existing, not by opting in:
        ``ScenarioSpec`` requires a story and ``@scenario`` requires
        ``story=`` (``test_a_scenario_cannot_register_without_a_story`` in
        ``test/demo_unit/story/test_assembly.py``). Asserted here because the
        alternative — an optional story the writer skips — would drop a
        scenario from the artifact with the drift check still green.
        """
        with pytest.raises(TypeError, match="story"):
            ScenarioSpec(  # type: ignore[call-arg]
                name=_FIXTURE_NAME,
                label="ZZ-plot",
                participants="Reporter + Vendor",
                feature="Fixture scenario; never registered",
                in_pr_set=False,
                path=((_BRANCH_POINT, _CHOICE),),
            )

    @pytest.mark.spec("DEMOCI-11-034")
    def test_the_manifest_names_the_command_that_rewrites_it(self) -> None:
        """A reader who found the file by grep learns not to hand-edit it."""
        payload = plot_manifest(
            (_fixture_spec(_ordered_story()),), WRITE_COMMAND
        )

        assert WRITE_COMMAND in payload["_README"]


# ---------------------------------------------------------------------------
# Unstable fragment names reach the rows (DEMOCI-11-034)
# ---------------------------------------------------------------------------
#
# The naming rule itself is pinned beside the function that owns it, in
# test/demo_unit/story/test_assembly.py (TestFragmentNames). What is asserted
# here is that the row builder routes through it: a guard reached only by a
# direct call covers nothing (#3156).


@pytest.mark.spec("DEMOCI-11-034")
def test_a_story_holding_an_unstable_name_is_refused_whole() -> None:
    """One lambda refuses the whole entry rather than writing the others."""
    unstable = story(
        choose(_BRANCH_POINT, _CHOICE, by=_DECIDED_BY),
        lambda state: None,
    )

    with pytest.raises(DemoStoryError, match="plot manifest cannot name"):
        plot_rows(_FIXTURE_NAME, unstable)


@pytest.mark.spec("DEMOCI-11-034")
def test_a_choose_is_not_read_as_a_fragment() -> None:
    """A choice takes the choice branch, not the fragment one.

    ``Choose`` is a ``slots=True`` dataclass, so an instance carries
    ``__module__`` but no ``__qualname__`` of its own: without the
    ``isinstance`` branch a choice would not be misnamed, it would be
    *refused* as unnameable, and the branch point it decides would never
    reach the manifest at all.
    """
    rows = plot_rows(
        _FIXTURE_NAME,
        story(choose(_BRANCH_POINT, _CHOICE, by=_DECIDED_BY)),
    )

    assert rows == [_CHOICE_ROW]
    assert isinstance(_ordered_story().items[0], Choose)
