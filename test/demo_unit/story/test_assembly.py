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
(DEMOCI-11-019, DEMOCI-11-024), and the named prefixes the registered
scenarios share (DEMOMA-17-001, DEMOMA-17-002).
"""

from __future__ import annotations

from typing import Any

import pytest

from test.demo_unit.story._support import (
    RV_CHOICES,
    make_fragment,
    rv_story,
)
from vultron.demo.helpers.story import (
    Choose,
    Story,
    choose,
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
