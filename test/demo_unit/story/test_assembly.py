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

"""How a story is written: choices, assembly, registration, prefixes.

Pins :mod:`vultron.demo.helpers.story.assembly`: :func:`choose` and
:func:`story`, the path a scenario's registration reads off its story
(DEMOCI-11-019, DEMOCI-11-024), the named prefixes the registered
scenarios share (DEMOMA-17-001, DEMOMA-17-002), :func:`fragment_name`, the
stable name the plot manifest records a fragment by (DEMOCI-11-034), and
:func:`fragment_sentence`, the one domain sentence each fragment's docstring
opens with, which the generated story renders its step as (DEMOCI-11-065,
DEMOCI-11-066).
"""

from __future__ import annotations

import functools
import re
from collections.abc import Callable
from typing import Any

import pytest

from test.demo_unit.story._support import (
    RV_CHOICES,
    make_fragment,
    rv_story,
)
from test.support.scenario_specs import fixture_spec
from vultron.demo.helpers.story import (
    Choose,
    Story,
    StoryState,
    choose,
    fragment_name,
    fragment_sentence,
    story,
)
from vultron.demo.scenario import registry
from vultron.demo.scenario.registry import (
    ScenarioSpec,
    discovery as registry_discovery,
    scenario,
)
from vultron.demo.scenario.tree import build_scenario_tree
from vultron.errors import (
    DemoScenarioRegistryError,
    DemoStoryError,
)


def _named_prefixes() -> dict[str, Story]:
    """Every named prefix the family's two story modules declare.

    ``{module.ATTRIBUTE: the prefix}``, deduplicated by the prefix object, so
    a prefix the embargo module imports to nest keeps the name of the module
    that declares it.  Derived rather than listed: a prefix is added each time
    a branch point of the family grows a second scenario, and a listed one
    would be checked only when a human remembered the row (#5534).
    """
    from vultron.demo.helpers import (
        coordinated_embargo_story,
        coordinated_story,
        two_coordinator_story,
    )

    prefixes: dict[str, Story] = {}
    seen: set[int] = set()
    # In declaration order, so a prefix a later module imports to nest keeps
    # the name of the module that declares it.
    for module in (
        coordinated_story,
        coordinated_embargo_story,
        two_coordinator_story,
    ):
        stem = module.__name__.rsplit(".", 1)[1]
        for attr, value in vars(module).items():
            if isinstance(value, Story) and id(value) not in seen:
                seen.add(id(value))
                prefixes[f"{stem}.{attr}"] = value
    return prefixes


def _registered_stories() -> dict[str, Story]:
    """``{scenario name: its story}`` for every registered scenario.

    Read from the registry rather than from a list of module names, so a new
    scenario composed onto one of these prefixes counts towards it the moment
    it is registered (DEMOCI-11-002).  A scenario with no ``STORY`` fails
    rather than drop out of every check that reads this, which is how a
    ``<name_>_demo/`` package whose ``__init__`` forgot to re-export it would
    otherwise slip past them (DEMOCI-11-003).
    """
    import importlib

    stories: dict[str, Story] = {}
    for spec in registry.discover_scenarios():
        plot = getattr(
            importlib.import_module(spec.module_name), "STORY", None
        )
        assert isinstance(plot, Story), (
            f"{spec.module_name} exposes no STORY; a package scenario's "
            "__init__ re-exports it beside main, ROLES and CLI_HELP"
        )
        stories[spec.name] = plot
    return stories


# ---------------------------------------------------------------------------
# choose(...) and story(...)
# ---------------------------------------------------------------------------


class TestChoose:
    @pytest.mark.spec("DEMOCI-11-013")
    def test_an_unknown_branch_point_is_refused_where_it_is_written(
        self,
    ) -> None:
        with pytest.raises(
            DemoScenarioRegistryError, match="unknown branch point"
        ):
            choose("no-such-branch-point", "vendor", by="reporter")

    @pytest.mark.spec("DEMOCI-11-013")
    def test_an_unknown_choice_is_refused_where_it_is_written(self) -> None:
        with pytest.raises(DemoScenarioRegistryError, match="no choice"):
            choose("reporter-whom-to-tell", "nobody", by="reporter")

    @pytest.mark.spec("DEMOCI-11-013", "DEMOCI-11-047")
    @pytest.mark.parametrize("by", ["", None])
    def test_a_choice_names_the_actor_that_decides(self, by: Any) -> None:
        with pytest.raises(DemoStoryError, match="as the actor that decides"):
            choose("reporter-whom-to-tell", "vendor", by=by)

    def test_the_step_is_the_branch_point_and_choice_pair(self) -> None:
        item = choose("reporter-whom-to-tell", "vendor", by="reporter")
        assert item.step == ("reporter-whom-to-tell", "vendor")


class TestStoryAssembly:
    def test_a_named_prefix_is_spliced_not_nested(self) -> None:
        """A prefix's items become the start of the whole, one flat sequence."""
        log: list[str] = []
        prefix = story(
            choose("reporter-whom-to-tell", "vendor", by="reporter"),
            make_fragment("submit", log),
        )
        whole = story(
            prefix,
            choose("vendor-after-answer", "report-fix-ready", by="vendor"),
            make_fragment("fix", log),
        )
        assert whole.items[:2] == prefix.items
        assert len(whole.items) == 4
        assert not any(isinstance(item, Story) for item in whole.items)

    @pytest.mark.spec("DEMOCI-11-019")
    def test_the_path_is_the_choices_in_order(self) -> None:
        assert rv_story().path == RV_CHOICES

    def test_a_story_with_no_items_is_refused(self) -> None:
        with pytest.raises(DemoStoryError, match="at least one item"):
            story()

    def test_a_part_that_is_not_an_item_is_refused(self) -> None:
        with pytest.raises(DemoStoryError, match="neither a named prefix"):
            story("reporter-whom-to-tell")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# @scenario(story=...) — the path is read off the story (DEMOCI-11-019)
# ---------------------------------------------------------------------------


def _register_fixture(
    monkeypatch: pytest.MonkeyPatch,
    *,
    name: str,
    story_obj: Story,
) -> ScenarioSpec:
    """Register a fixture scenario in an isolated copy of the registry."""
    monkeypatch.setattr(
        registry_discovery, "_REGISTRY", dict(registry_discovery._REGISTRY)
    )
    registry_discovery._REGISTRY.pop(name, None)
    decorate = scenario(
        name=name,
        label=name.upper(),
        participants="Reporter + Vendor",
        feature="Fixture",
        in_pr_set=False,
        story=story_obj,
    )

    def fixture_main() -> None:
        """Stand in for a composed scenario's main()."""

    fixture_main.__module__ = "test.demo_unit.test_story"
    decorate(fixture_main)
    return registry_discovery._REGISTRY[name]


def _fixture_spec_with(story_obj: Story) -> ScenarioSpec:
    """A spec for ``rv`` carrying *story_obj*, built without registering it."""
    return fixture_spec(
        name="rv", label="RV", feature="Fixture", story=story_obj
    )


class TestRegisteringAStory:
    @pytest.mark.spec("DEMOCI-11-019")
    def test_a_scenarios_path_is_its_storys_choices(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The derived path is the one the fixture registry's tree holds."""
        composed = rv_story()
        spec = _register_fixture(monkeypatch, name="rv", story_obj=composed)
        assert spec.path == composed.path

        tree = build_scenario_tree(registry.registered_scenarios())
        assert tree.endings()["rv"].prefix == composed.path

    @pytest.mark.spec("DEMOCI-11-014", "DEMOCI-11-024")
    def test_a_scenario_cannot_register_without_a_story(self) -> None:
        """``story`` is required, so there is no second way to declare a path.

        A ``TypeError`` rather than a ``DemoScenarioRegistryError``: the
        registry no longer accepts a spec with nowhere to sit, so the refusal
        is the signature's, at import, before any check could run.
        """
        with pytest.raises(TypeError, match="story"):
            scenario(  # type: ignore[call-arg]
                name="rv",
                label="RV",
                participants="Reporter + Vendor",
                feature="Fixture",
                in_pr_set=False,
            )

    @pytest.mark.spec("DEMOCI-11-001")
    def test_re_executing_a_scenario_module_registers_the_same_spec(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Re-running a module's decorator is the same scenario, not a conflict.

        ``_register`` decides "same scenario or conflict" by comparing specs,
        and a story's fragments are function objects compared by identity, so
        a re-executed module builds fresh ones. The spec keeps its story out
        of ``__eq__`` for exactly this reason; without that, every
        ``importlib.reload`` of a scenario whose story holds a fragment
        defined in its own module — most of them — would raise, and the
        one teardown that reloads one would go red far from its cause
        (``test/demo/test_rcv_demo.py``).
        """
        monkeypatch.setattr(
            registry_discovery,
            "_REGISTRY",
            dict(registry_discovery._REGISTRY),
        )
        first = _fixture_spec_with(rv_story())
        # A second story built the way a re-executed module's module-level
        # `story(...)` call builds it: equal in meaning, new objects.
        reread = _fixture_spec_with(rv_story())
        assert reread.story is not first.story

        registry_discovery._REGISTRY["rv"] = first
        registry_discovery._register(reread, "test.demo_unit.test_story")

        assert registry_discovery._REGISTRY["rv"] is reread

    @pytest.mark.spec("DEMOCI-11-034")
    def test_a_story_that_cannot_say_what_its_items_are_is_refused(
        self,
    ) -> None:
        """The exporter reads the items long after import, so import checks them.

        A stand-in carrying only ``path`` registers fine and then dies in the
        plot-manifest exporter as an ``AttributeError`` over an anonymous
        object, in a layer whose error messages are the product. The scenario
        name is asserted because naming it is the whole point of refusing
        here rather than there.
        """

        class _PathOnly:
            path = (("reporter-whom-to-tell", "vendor"),)

        with pytest.raises(
            DemoScenarioRegistryError, match="no items"
        ) as raised:
            scenario(
                name="rv",
                label="RV",
                participants="Reporter + Vendor",
                feature="Fixture",
                in_pr_set=False,
                story=_PathOnly(),  # type: ignore[arg-type]
            )

        assert "rv" in str(raised.value)

    @pytest.mark.spec("DEMOCI-11-034")
    def test_a_story_whose_items_are_mutable_is_refused(self) -> None:
        """A list of items could be rewritten behind the committed manifest.

        The scenario name is asserted for the same reason as above.
        """

        class _MutableItems:
            path = (("reporter-whom-to-tell", "vendor"),)
            items = [choose("reporter-whom-to-tell", "vendor", by="reporter")]

        with pytest.raises(
            DemoScenarioRegistryError, match="not a tuple"
        ) as raised:
            scenario(
                name="rv",
                label="RV",
                participants="Reporter + Vendor",
                feature="Fixture",
                in_pr_set=False,
                story=_MutableItems(),  # type: ignore[arg-type]
            )

        assert "rv" in str(raised.value)

    @pytest.mark.spec("DEMOCI-11-019")
    def test_a_story_that_names_no_path_is_refused(self) -> None:
        """A required argument can still arrive as a ``None``.

        A module-level ``STORY`` that resolved to ``None`` would otherwise
        reach the spec as an ``AttributeError`` naming no scenario.
        """
        with pytest.raises(DemoScenarioRegistryError, match="names no path"):
            scenario(
                name="rv",
                label="RV",
                participants="Reporter + Vendor",
                feature="Fixture",
                in_pr_set=False,
                story=None,  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# Every scenario keeps its place on the tree (DEMOMA-17-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DEMOCI-11-019", "DEMOMA-17-002")
@pytest.mark.parametrize(
    ("module_name", "expected"),
    [
        (
            "vultron.demo.scenario.rcv_demo",
            (
                ("reporter-whom-to-tell", "coordinator"),
                ("coordinator-invite-whom", "vendor"),
                ("vendor-join", "accept"),
                ("reporter-after-join", "ask-vendor"),
                ("coordinator-after-answer", "publish"),
            ),
        ),
        (
            "vultron.demo.scenario.rcv_reject_demo",
            (
                ("reporter-whom-to-tell", "coordinator"),
                ("coordinator-invite-whom", "vendor"),
                ("vendor-join", "reject"),
            ),
        ),
        (
            "vultron.demo.scenario.rcvcv_demo",
            (
                ("reporter-whom-to-tell", "coordinator"),
                ("coordinator-invite-whom", "vendor"),
                ("vendor-join", "accept"),
                ("reporter-after-join", "ask-vendor"),
                ("coordinator-after-answer", "invite-coordinator"),
            ),
        ),
        (
            "vultron.demo.scenario.rcv_embargo_demo",
            (
                ("reporter-whom-to-tell", "coordinator"),
                ("coordinator-invite-whom", "vendor"),
                ("vendor-join", "accept"),
                ("reporter-after-join", "propose-embargo"),
                ("vendor-after-embargo", "report-fix-ready"),
            ),
        ),
        (
            "vultron.demo.scenario.rcvv_embargo_demo",
            (
                ("reporter-whom-to-tell", "coordinator"),
                ("coordinator-invite-whom", "vendor"),
                ("vendor-join", "accept"),
                ("reporter-after-join", "propose-embargo"),
                ("vendor-after-embargo", "propose-revision"),
            ),
        ),
        (
            "vultron.demo.scenario.rccv_extension_demo",
            (
                ("reporter-whom-to-tell", "coordinator"),
                ("coordinator-invite-whom", "coordinator"),
                ("owner-keep-case", "keep"),
            ),
        ),
        (
            "vultron.demo.scenario.rccv_handoff_demo",
            (
                ("reporter-whom-to-tell", "coordinator"),
                ("coordinator-invite-whom", "coordinator"),
                ("owner-keep-case", "offer-ownership"),
            ),
        ),
    ],
)
def test_a_scenario_keeps_the_path_it_declared(
    module_name: str, expected: tuple[tuple[str, str], ...]
) -> None:
    """Story migration moved the code, not the scenario's place on the tree.

    Pinned against literals rather than against the registry, which would
    compare the derivation with itself.
    """
    import importlib

    module = importlib.import_module(module_name)
    assert module.STORY.path == expected


@pytest.mark.spec("DEMOMA-17-001")
def test_both_scenarios_share_one_opening() -> None:
    """``rcv`` and ``rcv-reject`` start from the same prefix object's items."""
    import importlib

    from vultron.demo.helpers.coordinated_story import (
        COORDINATOR_INVITES_VENDOR,
    )

    rcv = importlib.import_module("vultron.demo.scenario.rcv_demo")
    rcv_reject = importlib.import_module(
        "vultron.demo.scenario.rcv_reject_demo"
    )
    shared = len(COORDINATOR_INVITES_VENDOR.items)
    assert rcv.STORY.items[:shared] == COORDINATOR_INVITES_VENDOR.items
    assert rcv_reject.STORY.items[:shared] == COORDINATOR_INVITES_VENDOR.items
    assert isinstance(rcv.STORY.items[shared], Choose)
    assert isinstance(rcv_reject.STORY.items[shared], Choose)


#: Every named prefix the family declares, read off the two story modules.
_NAMED_PREFIXES = _named_prefixes()


#: Which named prefix nests which, outer first.  This is the content the
#: retired per-prefix scenario lists carried: the family parts at one branch
#: point per prefix, so each prefix beyond the opening carries an earlier one
#: whole rather than restating its steps (#5534).  Which *scenarios* start
#: from each prefix is no longer listed — it is read off the registry by
#: :func:`test_every_named_prefix_opens_at_least_two_scenarios`, so a fourth
#: prefix is checked without a human adding a row.
_PREFIX_NESTING = [
    (
        "coordinated_story.REPORTER_TELLS_THE_COORDINATOR",
        "coordinated_story.COORDINATOR_INVITES_VENDOR",
    ),
    (
        "coordinated_story.REPORTER_TELLS_THE_COORDINATOR",
        "two_coordinator_story.C1_INVITES_C2",
    ),
    (
        "coordinated_story.COORDINATOR_INVITES_VENDOR",
        "coordinated_story.VENDOR_JOINS_THE_CASE",
    ),
    (
        "coordinated_story.VENDOR_JOINS_THE_CASE",
        "coordinated_story.REPORTER_ASKS_THE_VENDOR",
    ),
    (
        "coordinated_story.VENDOR_JOINS_THE_CASE",
        "coordinated_embargo_story.REPORTER_PROPOSES_EMBARGO",
    ),
]


def test_the_named_prefixes_were_collected() -> None:
    """The guard the parametrized check below cannot carry itself.

    An empty derivation makes ``parametrize`` emit one skipped test and a
    green run (``empty_parameter_set_mark`` defaults to ``skip``), so the
    zero-target case needs its own assertion (DF-09-007).  Its sibling
    :func:`test_every_story_prop_name_is_unique` carries the same guard
    inline, where its subject is a dict it builds itself.
    """
    assert _NAMED_PREFIXES, (
        "no named prefix was collected, so the check below proves nothing; "
        "the prefixes have moved out of coordinated_story and "
        "coordinated_embargo_story and _named_prefixes needs the new modules"
    )


@pytest.mark.spec("DEMOMA-17-001")
@pytest.mark.spec("DEMOCI-11-018")
@pytest.mark.parametrize("prefix_name", sorted(_NAMED_PREFIXES))
def test_every_named_prefix_opens_at_least_two_scenarios(
    prefix_name: str,
) -> None:
    """A named prefix is a stretch that is *shared*, or it is not one.

    One scenario's opening needs no name: the fragments read top to bottom in
    its own module.  A prefix earns its name by being the opening two or more
    siblings start from, which is what keeps them from drifting
    (DEMOMA-17-001).  Each sibling is compared against the prefix object's own
    items rather than against a copy of the steps: assembling siblings from
    fragments alone lets one slip a step in before the branch point, which the
    byte-identity check would catch only after a regeneration.  The item right
    after the prefix must be a choice — that is the branch point they part at.
    """
    prefix = _NAMED_PREFIXES[prefix_name]
    shared = len(prefix.items)
    opened = {
        name: plot
        for name, plot in _registered_stories().items()
        if plot.items[:shared] == prefix.items
    }
    assert len(opened) >= 2, (
        f"{prefix_name} opens {sorted(opened)}; a named prefix is the opening "
        "at least two scenarios share, and a stretch only one walks belongs "
        "in that scenario's own module"
    )
    for name, plot in opened.items():
        assert len(plot.items) > shared, (
            f"{name} is {prefix_name} and nothing else, so the prefix is its "
            "whole story rather than an opening it parts from"
        )
        assert isinstance(plot.items[shared], Choose), (
            f"{name} places a step before the branch point it parts at"
        )


@pytest.mark.spec("DEMOMA-17-001")
@pytest.mark.spec("DEMOCI-11-018")
@pytest.mark.parametrize(("outer", "inner"), _PREFIX_NESTING)
def test_a_named_prefix_nests_the_shorter_one_it_carries(
    outer: str, inner: str
) -> None:
    """``inner`` opens with ``outer``'s own items, not a second copy of them.

    The nesting is why one correction to the family's opening reaches every
    scenario: the longer prefix splices the shorter (``story()`` flattens), so
    a step added to the opening cannot reach four siblings and miss the fifth.
    """
    assert _NAMED_PREFIXES[inner].items[
        : len(_NAMED_PREFIXES[outer].items)
    ] == (_NAMED_PREFIXES[outer].items), (
        f"{inner} restates {outer}'s steps instead of nesting it"
    )


@pytest.mark.spec("DEMOMA-13-012")
@pytest.mark.spec("DEMOMA-14-017")
def test_the_two_coordinator_pair_shares_the_second_invite_opening() -> None:
    """Both ``rccv`` scenarios start from ``C1_INVITES_C2`` (#5535).

    Which two they are, where the derived check above only knows there are at
    least two.  The pair's own prefix nests
    ``REPORTER_TELLS_THE_COORDINATOR`` (``_PREFIX_NESTING``) and carries on
    through C2 being seeded, invited and joined, so the pair parts at exactly
    one decision: whether the owner keeps the case.
    """
    import importlib

    from vultron.demo.helpers.two_coordinator_story import C1_INVITES_C2

    shared = len(C1_INVITES_C2.items)
    for stem in ("rccv_extension", "rccv_handoff"):
        module = importlib.import_module(f"vultron.demo.scenario.{stem}_demo")
        assert module.STORY.items[:shared] == C1_INVITES_C2.items, (
            f"{stem} does not start from C1_INVITES_C2"
        )
        assert isinstance(module.STORY.items[shared], Choose)
    assert C1_INVITES_C2.path[-1] == ("coordinator-invite-whom", "coordinator")


@pytest.mark.spec("DEMOMA-12-017")
@pytest.mark.spec("DEMOMA-13-012")
def test_every_coordinator_first_scenario_shares_one_report_submission() -> (
    None
):
    """All seven start from ``REPORTER_TELLS_THE_COORDINATOR`` (#5535).

    One copy of the report submission and the owner's triage, which is what
    makes the first thirteen ledger entries of every coordinator-first
    recording byte-identical (DEMOCI-11-018).  The scenario list is read off
    the registry's paths rather than typed, so an eighth joins the check by
    declaring ``reporter-whom-to-tell:coordinator``.
    """
    from vultron.demo.helpers.coordinated_story import (
        REPORTER_TELLS_THE_COORDINATOR,
    )

    shared = len(REPORTER_TELLS_THE_COORDINATOR.items)
    coordinator_first = {
        name: plot
        for name, plot in _registered_stories().items()
        if plot.path
        and plot.path[0] == ("reporter-whom-to-tell", "coordinator")
    }
    assert len(coordinator_first) >= 7, (
        f"only {sorted(coordinator_first)} tell a Coordinator first; the "
        "coordinator-first subtree has seven scenarios (#5535)"
    )
    for name, plot in coordinator_first.items():
        assert plot.items[:shared] == REPORTER_TELLS_THE_COORDINATOR.items, (
            f"{name} does not start from REPORTER_TELLS_THE_COORDINATOR, so "
            "its report submission is a second copy of the code"
        )


@pytest.mark.spec("DEMOMA-20-013")
@pytest.mark.spec("DEMOMA-21-015")
def test_the_embargo_pair_shares_the_proposal_opening() -> None:
    """Both embargo scenarios start from ``REPORTER_PROPOSES_EMBARGO``.

    Which two they are, where the derived check above only knows there are at
    least two.  The pair's own prefix nests ``VENDOR_JOINS_THE_CASE``
    (``_PREFIX_NESTING``) and carries on through the default embargo's
    confirmation, the Reporter's revision of it and the note thread that
    follows.
    """
    import importlib

    from vultron.demo.helpers.coordinated_embargo_story import (
        REPORTER_PROPOSES_EMBARGO,
    )

    shared = len(REPORTER_PROPOSES_EMBARGO.items)
    for stem in ("rcv_embargo", "rcvv_embargo"):
        module = importlib.import_module(f"vultron.demo.scenario.{stem}_demo")
        assert (
            module.STORY.items[:shared] == REPORTER_PROPOSES_EMBARGO.items
        ), f"{stem} does not start from REPORTER_PROPOSES_EMBARGO"
        assert isinstance(module.STORY.items[shared], Choose)


# ---------------------------------------------------------------------------
# How a written-down fragment is named (DEMOCI-11-034)
# ---------------------------------------------------------------------------


def reporter_submits_the_report(state: StoryState) -> None:
    """Stand in for a module-level fragment; only its name is read here."""


def _nested_fragment() -> Callable[[StoryState], None]:
    """Return a closure, whose qualified name holds ``<locals>``."""

    def inner(state: StoryState) -> None:
        """Stand in for a step written inside another function."""

    return inner


class _CallableStep:
    """A callable instance, which carries no ``__qualname__`` of its own."""

    def __call__(self, state: StoryState) -> None:
        """Stand in for a step written as an object."""


class TestFragmentNames:
    """``fragment_name`` is what the plot manifest records a fragment by.

    Its consumer is ``vultron/metadata/demo_scenarios/plots.py``, whose own
    tests pin the artifact; these pin the rule.
    """

    @pytest.mark.spec("DEMOCI-11-034")
    def test_a_module_level_fragment_is_named_by_module_and_qualname(
        self,
    ) -> None:
        assert (
            fragment_name(reporter_submits_the_report, scenario="rv")
            == f"{__name__}.reporter_submits_the_report"
        )

    @pytest.mark.spec("DEMOCI-11-034")
    @pytest.mark.parametrize(
        ("fragment", "match"),
        [
            (lambda state: None, "synthetic segment"),
            (_nested_fragment(), "synthetic segment"),
            (
                functools.partial(reporter_submits_the_report),
                "no __module__ and __qualname__ pair",
            ),
            (_CallableStep(), "no __module__ and __qualname__ pair"),
        ],
        ids=["lambda", "closure", "partial", "callable-instance"],
    )
    def test_an_unstable_name_is_refused(
        self, fragment: Callable[[StoryState], None], match: str
    ) -> None:
        """No name is handed back for one that says nothing about the step.

        A closure and a lambda are both ``<...>``-named, and neither a
        ``functools.partial`` nor a callable instance has a ``__qualname__``
        of its own — each would record a row that moves on an unrelated
        rename, or no row at all.
        """
        with pytest.raises(DemoStoryError, match=match) as raised:
            fragment_name(fragment, scenario="rv")

        assert "rv" in str(raised.value)


def the_vendor_validates_the_report(state: StoryState) -> None:
    """The Vendor validates the Reporter's report and engages the case."""


def the_vendor_tells_the_coordinator(state: StoryState) -> None:
    """The Vendor tells the Coordinator it has validated the report and
    engaged the case.

    Body prose a story never shows, because a step's line is its opening
    sentence alone.
    """


def _fragment_with_no_docstring(state: StoryState) -> None:
    pass


def _fragment_with_no_full_stop(state: StoryState) -> None:
    """The Vendor validates the Reporter's report"""


def _fragment_with_two_sentences(state: StoryState) -> None:
    """The Vendor validates the report. Then it engages the case."""


def _fragment_with_two_sentences_split_on_a_question(
    state: StoryState,
) -> None:
    """Does the Vendor accept? It accepts and triages the report."""


def _fragment_with_two_sentences_split_on_an_exclamation(
    state: StoryState,
) -> None:
    """The embargo holds! The Vendor keeps the fix unreleased."""


def _fragment_with_two_sentences_split_inside_a_quote(
    state: StoryState,
) -> None:
    """The Vendor answers "it holds." The Reporter agrees."""


def _fragment_with_two_sentences_split_inside_a_paren(
    state: StoryState,
) -> None:
    """The Vendor engages (as agreed.) The Reporter is told."""


def _fragment_with_a_word_ending_in_an_abbreviation(
    state: StoryState,
) -> None:
    """The Vendor's revs. The Reporter replies."""


def _fragment_naming_dotted_code(state: StoryState) -> None:
    """The Reporter publishes; CS.P ends the embargo."""


def _fragment_naming_a_dotted_name_and_its_tail(state: StoryState) -> None:
    """The role CVDRole.CASE_OWNER decides."""


def _fragment_naming_the_container_word_twice(state: StoryState) -> None:
    """The container holds containers."""


def _fragment_naming_an_abbreviated_place(state: StoryState) -> None:
    """The Vendor, a U.S. supplier, engages the case."""


def _fragment_naming_the_container_word(state: StoryState) -> None:
    """The Vendor's container holds the authoritative case."""


def _fragment_with_a_milestone_marker(state: StoryState) -> None:
    """M1: the Reporter and the Vendor are seated."""


def _fragment_with_an_abbreviation(state: StoryState) -> None:
    """The Vendor, Acme Inc. of Pittsburgh, engages the case."""


def _fragment_ending_in_a_quote(state: StoryState) -> None:
    '''The Vendor answers "the embargo holds."'''


def _fragment_with_a_backtick(state: StoryState) -> None:
    """The fix being ready leaves the embargo in force (``EM.ACTIVE``)."""


def _fragment_naming_an_identifier(state: StoryState) -> None:
    """The Vendor, as CASE_OWNER, publishes its advisory first."""


def _fragment_naming_a_container(state: StoryState) -> None:
    """The Reporter submits its report to actor1."""


def _fragment_naming_the_case_actor_container(state: StoryState) -> None:
    """The case-actor records the Vendor's engagement."""


class TestFragmentSentences:
    """``fragment_sentence`` is how a fragment says what its step does.

    Its consumer is ``vultron/metadata/demo_scenarios/stories.py``, whose own
    tests pin the generated artifact; these pin the rule (DEMOCI-11-065,
    DEMOCI-11-066).
    """

    @pytest.mark.spec("DEMOCI-11-065")
    def test_the_opening_sentence_is_the_docstrings_first_sentence(
        self,
    ) -> None:
        assert (
            fragment_sentence(the_vendor_validates_the_report, scenario="rv")
            == "The Vendor validates the Reporter's report and engages the "
            "case."
        )

    @pytest.mark.spec("DEMOCI-11-065")
    def test_a_wrapped_summary_is_joined_into_one_line(self) -> None:
        """A summary long enough to wrap is still one sentence.

        Reading only the docstring's first physical line would cut it in
        half and render half a sentence as the step.
        """
        assert fragment_sentence(
            the_vendor_tells_the_coordinator, scenario="rv"
        ) == (
            "The Vendor tells the Coordinator it has validated the report "
            "and engaged the case."
        )

    @pytest.mark.spec("DEMOCI-11-065", "DEMOCI-11-066")
    @pytest.mark.parametrize(
        ("fragment", "match"),
        [
            (_fragment_with_no_docstring, "has no docstring"),
            (_fragment_with_no_full_stop, "does not end in a full stop"),
            (_fragment_with_two_sentences, "more than one sentence"),
            (
                _fragment_with_two_sentences_split_on_a_question,
                "more than one sentence",
            ),
            (
                _fragment_with_two_sentences_split_on_an_exclamation,
                "more than one sentence",
            ),
            (
                _fragment_with_two_sentences_split_inside_a_quote,
                "more than one sentence",
            ),
            (
                _fragment_with_two_sentences_split_inside_a_paren,
                "more than one sentence",
            ),
            (
                _fragment_with_a_word_ending_in_an_abbreviation,
                "more than one sentence",
            ),
            (_fragment_with_a_backtick, "holds a backtick"),
            (_fragment_naming_an_identifier, "'CASE_OWNER'"),
            (_fragment_naming_dotted_code, "'CS.P'"),
            (_fragment_naming_a_container, "container 'actor1'"),
            (
                _fragment_naming_the_case_actor_container,
                "container 'case-actor'",
            ),
            (
                _fragment_naming_the_container_word,
                "container 'container'",
            ),
            (_fragment_with_a_milestone_marker, "milestone marker"),
        ],
        ids=[
            "no-docstring",
            "no-full-stop",
            "two-sentences",
            "two-sentences-question",
            "two-sentences-exclamation",
            "two-sentences-closing-quote",
            "two-sentences-closing-paren",
            "two-sentences-word-ending-in-an-abbreviation",
            "backtick",
            "identifier",
            "dotted-identifier",
            "actor-container",
            "case-actor-container",
            "container-word",
            "milestone-marker",
        ],
    )
    def test_a_sentence_that_is_not_domain_prose_is_refused(
        self, fragment: Callable[[StoryState], None], match: str
    ) -> None:
        """Each way a docstring fails to be one domain sentence is reported.

        A rendering of any of these is the plot manifest's code name again,
        which is the one thing the story exists to replace.
        """
        with pytest.raises(DemoStoryError, match=re.escape(match)) as raised:
            fragment_sentence(fragment, scenario="rv")

        assert "rv" in str(raised.value)

    @pytest.mark.spec("DEMOCI-11-065")
    @pytest.mark.parametrize(
        "fragment",
        [
            _fragment_with_an_abbreviation,
            _fragment_ending_in_a_quote,
            _fragment_naming_an_abbreviated_place,
        ],
        ids=["abbreviation", "closing-quote", "abbreviation-with-a-capital"],
    )
    def test_a_legitimate_single_sentence_is_not_refused(
        self, fragment: Callable[[StoryState], None]
    ) -> None:
        """Neither an abbreviation's full stop nor a closing quote is an end.

        Both were false refusals, and the message then told the author to
        move a remainder into the docstring's body that was not there. The
        third is the pair of them: ``U.S.`` is followed by a capital, so
        before the two checks read one blanked text it was refused twice
        over — as two sentences *and* as the code identifier ``U.S``.
        """
        assert fragment_sentence(fragment, scenario="rv").startswith(
            "The Vendor"
        )

    @pytest.mark.spec("EH-07-001")
    @pytest.mark.parametrize(
        ("fragment", "prefix", "named"),
        [
            (
                _fragment_naming_a_dotted_name_and_its_tail,
                "it names the code identifier",
                "'CVDRole.CASE_OWNER'",
            ),
            (
                _fragment_naming_the_container_word_twice,
                "it names the container",
                "'container'",
            ),
        ],
        ids=["dotted-name-and-its-tail", "container-word-and-its-plural"],
    )
    def test_one_offence_is_one_line(
        self,
        fragment: Callable[[StoryState], None],
        prefix: str,
        named: str,
    ) -> None:
        """Two spellings of one offence are not two violations.

        A dotted name's tail is an underscore-joined name too, and the plural
        of a container word is the same word, so each used to print a second
        line naming half of what the first line already named.
        """
        with pytest.raises(DemoStoryError) as raised:
            fragment_sentence(fragment, scenario="rv")

        reported = str(raised.value)
        assert reported.count(prefix) == 1
        assert named in reported

    @pytest.mark.spec("EH-07-001")
    def test_one_identifier_named_twice_is_reported_once(self) -> None:
        """A kind of violation is reported once, however often it occurs."""
        with pytest.raises(DemoStoryError) as raised:
            fragment_sentence(_fragment_repeating_an_identifier, scenario="rv")

        assert str(raised.value).count("'add_note'") == 1

    @pytest.mark.spec("DEMOCI-11-066")
    def test_every_violation_of_one_sentence_is_reported(self) -> None:
        """One message names all of them, not only the first (EH-07-001).

        The sentence is refused as a unit, so an author told one reason per
        round trip learns the next one only by fixing this one.
        """
        with pytest.raises(DemoStoryError) as raised:
            fragment_sentence(_bad_in_every_way, scenario="rv")

        reported = str(raised.value)
        assert "does not end in a full stop" in reported
        assert "holds a backtick" in reported
        assert "'CASE_OWNER'" in reported
        assert "container 'actor0'" in reported

    @pytest.mark.spec("DEMOCI-11-065")
    def test_a_fragment_with_no_stable_name_is_refused(self) -> None:
        """A step that cannot be named cannot be read either.

        ``functools.partial`` answers ``__doc__`` with its own class's
        docstring, which ends in a full stop, holds no backtick and names no
        identifier — so it would pass every sentence check and render "Create
        a new function with partial application of the given arguments and
        keywords." as a step. The naming rule refuses it first.
        """
        fragment = functools.partial(the_vendor_validates_the_report)

        with pytest.raises(DemoStoryError, match="cannot name"):
            fragment_sentence(fragment, scenario="rv")

    @pytest.mark.spec("DEMOCI-11-065")
    def test_every_fragment_name_is_also_a_sentence(self) -> None:
        """Both rules hold of the same fragment, and neither implies the other.

        ``fragment_name`` answers "can this step be recorded?" and
        ``fragment_sentence`` "can this step be read?". A fragment that
        passes one may fail the other, so the plot manifest and the generated
        story each call their own.
        """
        fragment = the_vendor_validates_the_report

        assert fragment_name(fragment, scenario="rv").endswith(
            "the_vendor_validates_the_report"
        )
        assert fragment_sentence(fragment, scenario="rv").startswith(
            "The Vendor"
        )


def _bad_in_every_way(state: StoryState) -> None:
    """The ``advisory`` is published by actor0, as CASE_OWNER"""


def _fragment_repeating_an_identifier(state: StoryState) -> None:
    """The add_note step repeats add_note."""
