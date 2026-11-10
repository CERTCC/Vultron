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

"""Shape, drift and page tests for the generated scenario stories.

``docs/topics/scenarios/_<scenario>-story.md`` renders one registered
scenario's plot as a numbered story in CVD domain terms, and that scenario's
narrative page includes it after the hand-written narrative (DEMOCI-11-067,
DEMOCI-11-068).  :mod:`vultron.metadata.demo_scenarios.sync` drift-checks
every one of them with the other registry artifacts (DEMOCI-11-005,
DEMOCI-11-069).

Four questions are asked here, and they fail for different reasons:

* **Every fragment can be read**
  (``test_every_fragment_in_the_manifest_opens_with_a_domain_sentence``) — the
  corpus assertion for DEMOCI-11-065 and DEMOCI-11-066.  The rule those rest
  on is pinned beside the function that owns it, in
  ``test/demo_unit/story/test_assembly.py`` (``TestFragmentSentences``).
* **The committed stories are the stories in the code** (``TestStoryDrift``) —
  the drift assertions, which name the regeneration command, and the
  empty-registry gate DF-09-009 asks for.
* **The rendering is the shape the spec names** (``TestStoryShape``) — a
  fragment as its opening sentence, a choice as its deciding role and the
  branch-point table's presenter label.
* **Every narrative page ends with its story** (``TestNarrativePages``) —
  with the negative cases, because a position check that cannot fail would
  leave the rendering anywhere on the page.

To fix a drift failure here::

    uv run demo-scenarios --write
    git add docs/topics/scenarios/
"""

from __future__ import annotations

import importlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from test.support.scenario_specs import fixture_spec
from vultron.demo.helpers.story import (
    Story,
    StoryState,
    choose,
    fragment_sentence,
    story,
)
from vultron.demo.scenario.branch_points import BRANCH_POINTS
from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError
from vultron.metadata.demo_scenarios import sync
from vultron.metadata.demo_scenarios.narrative_pages import NARRATIVE_DIR
from vultron.metadata.demo_scenarios.plots import (
    FRAGMENT_KIND,
    PLOT_MANIFEST,
)
from vultron.metadata.demo_scenarios.stories import (
    DECIDING_ROLE_LABELS,
    STORY_HEADING,
    STORY_SECTION,
    choice_line,
    include_directive,
    missing_story_includes,
    orphan_story_fragments,
    render_story,
    story_fragments,
    story_lines,
    story_path,
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
_FIXTURE_NAME = "zz-story"

#: The fixture's one decision, a real branch-point table entry so ``choose``
#: validates it as a scenario's own would.
_BRANCH_POINT = "reporter-whom-to-tell"
_CHOICE = "vendor"
_DECIDED_BY = "reporter"


def the_reporter_tells_the_vendor(state: StoryState) -> None:
    """The Reporter submits its report; the Vendor engages the case."""


def the_vendor_engages_the_case_in_code(state: StoryState) -> None:
    """The Vendor, as CASE_OWNER, engages the case."""


def _fixture_story() -> Story:
    """The fixture story: the decision, then the step it decides."""
    return story(
        choose(_BRANCH_POINT, _CHOICE, by=_DECIDED_BY),
        the_reporter_tells_the_vendor,
    )


def _fixture_spec(plot: Story) -> ScenarioSpec:
    """A spec carrying *plot* as its story."""
    return fixture_spec(name=_FIXTURE_NAME, label="ZZ-story", story=plot)


def _manifest_fragments() -> list[tuple[str, str]]:
    """Return ``(scenario, qualified name)`` for every fragment the plot names.

    Read from the committed manifest rather than from the registry, because
    DEMOCI-11-065's subject is "every fragment the plot manifest names": the
    manifest is the enumeration, and a fragment that reached it is one a
    reader of a story will meet.
    """
    text = read_committed(_REPO_ROOT / PLOT_MANIFEST)
    assert text, (
        f"{PLOT_MANIFEST} is missing or empty. Run '{WRITE_COMMAND}' and "
        f"commit it (DEMOCI-11-034)."
    )
    scenarios = json.loads(text)["scenarios"]
    named = [
        (scenario, row["name"])
        for scenario, rows in scenarios.items()
        for row in rows
        if row["kind"] == FRAGMENT_KIND
    ]
    assert named, (
        f"{PLOT_MANIFEST} names no fragment, so this check would pass over "
        f"every one of them (DF-09-009). Run '{WRITE_COMMAND}'."
    )
    return named


def _resolve(qualified_name: str) -> object:
    """Import and return the fragment *qualified_name* names."""
    module, _dot, attribute = qualified_name.rpartition(".")
    return getattr(importlib.import_module(module), attribute)


# ---------------------------------------------------------------------------
# Every fragment can be read (DEMOCI-11-065, DEMOCI-11-066)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOCI-11-065", "DEMOCI-11-066")
def test_every_fragment_in_the_manifest_opens_with_a_domain_sentence() -> None:
    """No fragment the plot names fails the rule the rendering rests on.

    Reported for every failing fragment at once rather than on the first:
    a run that names one of them makes an author fix it and learn about the
    next on the next run.
    """
    refused: list[str] = []
    for scenario, name in _manifest_fragments():
        try:
            fragment_sentence(_resolve(name), scenario=scenario)
        except DemoStoryError as error:
            refused.append(str(error))

    assert not refused, "\n".join(refused)


# ---------------------------------------------------------------------------
# Shape (DEMOCI-11-068)
# ---------------------------------------------------------------------------


class TestStoryShape:
    @pytest.mark.spec("DEMOCI-11-068")
    def test_a_fragment_renders_as_its_opening_sentence(self) -> None:
        """And a choice as its deciding role and the table's presenter label."""
        assert story_lines(_FIXTURE_NAME, _fixture_story()) == [
            "Reporter decides: Report it to the Vendor",
            "The Reporter submits its report; the Vendor engages the case.",
        ]

    @pytest.mark.spec("DEMOCI-11-068")
    def test_the_lines_are_numbered_in_story_order(self) -> None:
        """The rendered fragment is a numbered list, in the story's order."""
        rendered = render_story(_FIXTURE_NAME, _fixture_story(), WRITE_COMMAND)

        assert rendered.endswith(
            "1. Reporter decides: Report it to the Vendor\n"
            "2. The Reporter submits its report; the Vendor engages the "
            "case.\n"
        )

    @pytest.mark.spec("DEMOCI-11-013", "DEMOCI-11-068")
    def test_a_choices_label_is_the_branch_point_tables(self) -> None:
        """The label is read from the table, never restated here.

        The table is where a prompt and a label are declared and nowhere
        else (DEMOCI-11-050), so this asserts the renderer reads it rather
        than comparing against a second copy.
        """
        branch_point = BRANCH_POINTS[_BRANCH_POINT]
        expected = branch_point.choice(_CHOICE).label

        assert (
            choice_line(choose(_BRANCH_POINT, _CHOICE, by=_DECIDED_BY))
            == f"Reporter decides: {expected}"
        )

    @pytest.mark.spec("DEMOCI-11-068")
    def test_every_role_has_a_story_label(self) -> None:
        """A branch point for any role renders, in the glossary's spelling.

        Derived labels were rejected because ``"cve_numbering_authority"``
        title-cases to "Cve Numbering Authority"; a branch point for a role
        with no label would raise instead, so the map is kept exhaustive
        here (CS-19-001).
        """
        assert set(DECIDING_ROLE_LABELS) == set(CVDRole)

    @pytest.mark.spec("DEMOCI-11-013", "DEMOCI-11-068")
    def test_every_branch_point_in_the_table_renders_its_own_label(
        self,
    ) -> None:
        """Each branch point renders with the role and label the table holds.

        The exhaustiveness test above cannot make this assertion: it pins the
        label map against ``CVDRole``, not the line a real branch point
        renders as.
        """
        for identifier, branch_point in BRANCH_POINTS.items():
            for choice in branch_point.choices:
                line = choice_line(
                    choose(identifier, choice.id, by=_DECIDED_BY)
                )
                assert line == (
                    f"{DECIDING_ROLE_LABELS[branch_point.role]} decides: "
                    f"{choice.label}"
                ), identifier

    @pytest.mark.spec("DEMOCI-11-067")
    def test_the_story_names_the_command_that_rewrites_it(self) -> None:
        """A reader who found the file by grep learns not to hand-edit it."""
        rendered = render_story(_FIXTURE_NAME, _fixture_story(), WRITE_COMMAND)

        assert WRITE_COMMAND in rendered
        assert _FIXTURE_NAME in rendered

    @pytest.mark.spec("DEMOCI-11-067")
    def test_one_story_is_rendered_per_registered_scenario(self) -> None:
        """Every spec gets an entry; none opts in or out."""
        specs = discover_scenarios()

        rendered = story_fragments(specs, WRITE_COMMAND)

        assert set(rendered) == {story_path(spec.name) for spec in specs}

    @pytest.mark.spec("DEMOCI-11-065", "DEMOCI-11-068")
    def test_a_fragment_with_no_readable_sentence_refuses_the_story(
        self,
    ) -> None:
        """One unreadable fragment refuses the whole rendering.

        Writing the other lines and skipping this one would publish a story
        with a step missing, which reads as a complete story that is wrong
        rather than as a failure.
        """
        unreadable = story(
            choose(_BRANCH_POINT, _CHOICE, by=_DECIDED_BY),
            the_vendor_engages_the_case_in_code,
        )

        with pytest.raises(DemoStoryError, match="cannot be told as a story"):
            story_lines(_FIXTURE_NAME, unreadable)


# ---------------------------------------------------------------------------
# Drift (DEMOCI-11-069)
# ---------------------------------------------------------------------------


class TestStoryDrift:
    @pytest.mark.spec("DEMOCI-11-005", "DEMOCI-11-069")
    def test_every_committed_story_matches_a_fresh_rendering(self) -> None:
        """The committed stories are what the registry's stories render today."""
        specs = discover_scenarios()
        stale = [
            path
            for path in stale_artifacts(_REPO_ROOT)
            if path in {story_path(spec.name) for spec in specs}
        ]

        assert not stale, (
            f"generated scenario stories are stale: {stale}. A story's items "
            f"or a fragment's opening sentence changed. Run "
            f"'{WRITE_COMMAND}' and commit the result (DEMOCI-11-069)."
        )

    @pytest.mark.spec("DEMOCI-11-069")
    def test_each_committed_story_is_its_scenarios_rendering(self) -> None:
        """Per scenario, the committed file is that story's rendering.

        The drift assertion above compares whole files, which names no
        scenario when it fails. This one fails on the scenario whose story
        moved, which is what a reader of a red run needs.
        """
        for spec in discover_scenarios():
            committed = read_committed(_REPO_ROOT / story_path(spec.name))
            assert committed == render_story(
                spec.name, spec.story, WRITE_COMMAND
            ), spec.name

    @pytest.mark.spec("DEMOCI-11-069")
    def test_a_hand_edited_story_is_reported_stale(
        self, story_root: Path
    ) -> None:
        """The gate is not vacuous: an edited line fails it."""
        target = story_root / story_path(_FIXTURE_NAME)
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "Report it to the Vendor", "hand-edited"
            ),
            encoding="utf-8",
        )

        stale = stale_artifacts(story_root, (_fixture_spec(_fixture_story()),))

        assert stale == [story_path(_FIXTURE_NAME)]

    @pytest.mark.spec("DEMOCI-11-069")
    def test_check_names_the_regeneration_command(
        self,
        story_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``--check`` exits 1 and names the command that rewrites the story.

        The prose consistency checks and the derived-path check are stubbed
        out for the same reasons as in ``test_plots.py``: in a one-scenario
        tree they would report every real page and table as a disagreement,
        and the fixture scenario has no demo module, which makes ``--check``
        stop naming ``--write`` at all.
        """
        specs = (_fixture_spec(_fixture_story()),)
        target = story_root / story_path(_FIXTURE_NAME)
        target.write_text("hand-edited\n", encoding="utf-8")
        monkeypatch.setattr(sync, "repo_root", lambda: story_root)
        monkeypatch.setattr(sync, "discover_scenarios", lambda: specs)
        monkeypatch.setattr(sync, "consistency_problems", lambda *_args: [])
        monkeypatch.setattr(sync, "missing_derived_paths", lambda *_args: [])

        with pytest.raises(SystemExit) as raised:
            sync.main(["--check"])

        assert raised.value.code == 1
        reported = capsys.readouterr().err
        assert story_path(_FIXTURE_NAME) in reported
        assert WRITE_COMMAND in reported

    @pytest.mark.spec("DEMOCI-11-069")
    def test_check_fails_on_an_empty_registry(
        self,
        story_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """No scenario to check is a failure, not a clean tree (DF-09-009).

        With an empty registry every per-scenario artifact — each page's
        generated story included — is compared against nothing, so a gate
        that passed here would pass over the whole set.
        """
        monkeypatch.setattr(sync, "repo_root", lambda: story_root)
        monkeypatch.setattr(sync, "discover_scenarios", lambda: ())

        with pytest.raises(SystemExit) as raised:
            sync.main(["--check"])

        assert raised.value.code == 1
        # The refusal is the whole output: with no scenario every declared
        # artifact also compares stale, and four lines pointing at a
        # regeneration that would make the tree worse is misdirection.
        assert capsys.readouterr().err == f"[ERROR] {sync.EMPTY_REGISTRY}\n"

    @pytest.mark.spec("DEMOCI-11-069")
    def test_write_refuses_an_empty_registry(
        self,
        story_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The writer refuses it too, rather than emptying every artifact.

        An empty registry renders the CI matrix as ``[]``, the plot manifest
        with no scenario and both README tables as header rows, and leaves
        every committed story orphaned — all of it reported as success.
        """
        committed = (story_root / sync.MATRIX_JSON).read_text(encoding="utf-8")
        monkeypatch.setattr(sync, "repo_root", lambda: story_root)
        monkeypatch.setattr(sync, "discover_scenarios", lambda: ())

        with pytest.raises(SystemExit) as raised:
            sync.main(["--write"])

        assert raised.value.code == 1
        assert capsys.readouterr().err == f"[ERROR] {sync.EMPTY_REGISTRY}\n"
        assert (story_root / sync.MATRIX_JSON).read_text(
            encoding="utf-8"
        ) == committed


@pytest.fixture
def story_root(tmp_path: Path) -> Path:
    """A tree whose artifacts are generated from the fixture scenario alone.

    The two markdown artifacts are spliced into hand-written prose that cannot
    be regenerated, so they are copied from the repository first; the
    whole-file artifacts and the one story are then written from the fixture
    spec. Starting from a one-scenario registry is what isolates each edit
    below: nothing else in the tree can be the reason an artifact is reported
    stale.
    """
    for artifact in ARTIFACTS:
        if artifact.whole_file:
            continue
        target = tmp_path / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_REPO_ROOT / artifact.path, target)
    write_artifacts(tmp_path, (_fixture_spec(_fixture_story()),))
    return tmp_path


# ---------------------------------------------------------------------------
# The narrative pages (DEMOCI-11-067)
# ---------------------------------------------------------------------------


class TestNarrativePages:
    @pytest.mark.spec("DEMOCI-11-067")
    def test_every_narrative_page_ends_with_its_story(self) -> None:
        """Each registered scenario's page includes its story, last."""
        assert missing_story_includes(_REPO_ROOT) == []

    @pytest.mark.spec("DEMOCI-11-067")
    def test_no_story_fragment_is_left_behind(self) -> None:
        """Every committed story belongs to a registered scenario."""
        assert orphan_story_fragments(_REPO_ROOT) == []

    @pytest.mark.spec("DEMOCI-11-067")
    def test_a_page_with_no_story_section_is_reported(
        self, page_root: Path
    ) -> None:
        """A page that never gained the section is named, with what it ends on."""
        spec = discover_scenarios()[0]
        target = page_root / spec.narrative_path
        text = target.read_text(encoding="utf-8")
        target.write_text(
            text.split(f"## {STORY_HEADING}")[0], encoding="utf-8"
        )

        reported = missing_story_includes(page_root)

        assert len(reported) == 1, reported
        assert reported[0].startswith(f"{spec.narrative_path} ends with ")
        assert f"'{STORY_SECTION}' section" in reported[0]

    @pytest.mark.spec("DEMOCI-11-067")
    def test_a_story_placed_before_the_narrative_is_reported(
        self, page_root: Path
    ) -> None:
        """The position is checked, not only the presence.

        A rendering spliced in among the narrative's own steps reads as part
        of the narrative, which is the one thing it must not do: the
        narrative is written without the code so that it can contradict it.
        """
        spec = discover_scenarios()[0]
        target = page_root / spec.narrative_path
        text = target.read_text(encoding="utf-8")
        head, _, _tail = text.partition(f"## {STORY_HEADING}")
        target.write_text(
            f"## {STORY_HEADING}\n\n{include_directive(spec.name)}\n\n{head}",
            encoding="utf-8",
        )

        reported = missing_story_includes(page_root)

        # The whole message, so this tells the "ends with the wrong heading"
        # shape from the "section has no include" one — but the heading it
        # ends with is read out of the message rather than pinned: that
        # heading belongs to whichever narrative page sorts first and is
        # incidental to what is being checked here.
        assert len(reported) == 1
        problem = reported[0]
        prefix = f"{spec.narrative_path} ends with "
        suffix = f", not with a '{STORY_SECTION}' section"
        assert problem.startswith(prefix), problem
        assert problem.endswith(suffix), problem
        ends_with = problem[len(prefix) : -len(suffix)]
        assert ends_with.startswith("'##"), ends_with
        assert STORY_HEADING not in ends_with, ends_with

    @pytest.mark.spec("DEMOCI-11-067")
    def test_a_section_with_no_include_is_reported(
        self, page_root: Path
    ) -> None:
        """The heading alone is not the story."""
        spec = discover_scenarios()[0]
        target = page_root / spec.narrative_path
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                include_directive(spec.name), "the story goes here"
            ),
            encoding="utf-8",
        )

        reported = missing_story_includes(page_root)

        assert reported == [
            f"{spec.narrative_path}'s '{STORY_SECTION}' section does not "
            f"include {story_path(spec.name)}"
        ]

    @pytest.mark.spec("DEMOCI-11-067")
    def test_an_absent_page_is_left_to_the_derived_path_check(
        self, page_root: Path
    ) -> None:
        """A registered scenario with no page at all is not reported twice.

        ``sync.missing_derived_paths`` already names it, under the
        requirement that owns the convention (DEMOCI-11-003).
        """
        spec = discover_scenarios()[0]
        (page_root / spec.narrative_path).unlink()

        assert missing_story_includes(page_root) == []

    @pytest.mark.spec("DEMOCI-11-067")
    def test_an_empty_page_is_reported(self, page_root: Path) -> None:
        """A page with no sections at all has nowhere for the story to be."""
        spec = discover_scenarios()[0]
        (page_root / spec.narrative_path).write_text("", encoding="utf-8")

        reported = missing_story_includes(page_root)

        assert reported == [
            f"{spec.narrative_path} ends with '(no heading)', not with a "
            f"'{STORY_SECTION}' section"
        ]

    @pytest.mark.spec("DEMOCI-11-067")
    def test_a_story_heading_nested_in_the_narrative_is_reported(
        self, page_root: Path
    ) -> None:
        """A ``###`` heading is a subsection of the narrative, not a section.

        This is the "spliced in among the narrative's own steps" case the
        check exists for, and the level is the only thing that tells it from
        a well-placed section.
        """
        spec = discover_scenarios()[0]
        target = page_root / spec.narrative_path
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                STORY_SECTION, f"### {STORY_HEADING}"
            ),
            encoding="utf-8",
        )

        reported = missing_story_includes(page_root)

        assert reported == [
            f"{spec.narrative_path} ends with '### {STORY_HEADING}', not "
            f"with a '{STORY_SECTION}' section"
        ]

    @pytest.mark.spec("DEMOCI-11-067")
    def test_a_directive_shown_in_a_code_block_is_not_an_include(
        self, page_root: Path
    ) -> None:
        """A page that documents the directive includes nothing.

        The fenced form renders as text, so the story never appears.
        """
        spec = discover_scenarios()[0]
        target = page_root / spec.narrative_path
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                include_directive(spec.name),
                f"```markdown\n{include_directive(spec.name)}\n```",
            ),
            encoding="utf-8",
        )

        reported = missing_story_includes(page_root)

        assert reported == [
            f"{spec.narrative_path}'s '{STORY_SECTION}' section does not "
            f"include {story_path(spec.name)}"
        ]

    @pytest.mark.spec("DEMOCI-11-067")
    def test_a_trailing_bare_heading_does_not_hide_the_story(
        self, page_root: Path
    ) -> None:
        """A heading with nothing under it is not where the story is.

        Without the skip, appending one empty section to a page would make
        the check report every page as missing its story.
        """
        spec = discover_scenarios()[0]
        target = page_root / spec.narrative_path
        target.write_text(
            target.read_text(encoding="utf-8") + "\n## See also\n",
            encoding="utf-8",
        )

        assert missing_story_includes(page_root) == []

    @pytest.mark.spec("DEMOCI-11-067")
    @pytest.mark.parametrize(
        "check",
        [missing_story_includes, orphan_story_fragments],
        ids=["includes", "orphans"],
    )
    def test_a_moved_narrative_directory_fails_both_checks(
        self,
        tmp_path: Path,
        check: Callable[[Path], list[str]],
    ) -> None:
        """A missing directory is an error, not an empty result (DF-09-009).

        Either check would otherwise find no page, report success, and drop
        every scenario out of coverage at once.
        """
        with pytest.raises(FileNotFoundError, match=NARRATIVE_DIR):
            check(tmp_path)

    @pytest.mark.spec("DEMOCI-11-067")
    def test_an_orphan_story_fragment_is_reported(
        self, page_root: Path
    ) -> None:
        """A retired scenario's leftover story is named for deletion."""
        orphan = page_root / story_path("zz-retired")
        orphan.write_text("1. Nobody tells this story.\n", encoding="utf-8")

        assert orphan_story_fragments(page_root) == [story_path("zz-retired")]


@pytest.fixture
def page_root(tmp_path: Path) -> Path:
    """A tree holding copies of every narrative page and generated story.

    Copied rather than generated so the page checks start from exactly what
    is committed; a fixture that wrote its own starting state could pass while
    the real pages were already wrong.
    """
    for spec in discover_scenarios():
        for path in (spec.narrative_path, story_path(spec.name)):
            target = tmp_path / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_REPO_ROOT / path, target)
    return tmp_path
