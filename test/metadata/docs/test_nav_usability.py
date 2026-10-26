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
"""The agent usability test harness that gates a nav change (ADR-0136)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from vultron.metadata.base import repo_root
from vultron.metadata.docs import nav_usability as nu
from vultron.metadata.file_loading import MetadataLoadError, MetadataLoadErrors

_PERSONA = {
    "id": "p1",
    "name": "Reader",
    "brief": "You read things.",
    "does_not_know": ["You do not know X."],
    "start_page": "start/a.md",
}
_THREAD = {
    "id": "T1",
    "persona": "p1",
    "kind": "thread",
    "prompt": "Where do I start?",
    "source": "thread",
}
_LOOKUP = {
    "id": "T2",
    "persona": "p1",
    "kind": "lookup",
    "prompt": "Find the embargo page.",
    "destinations": ["topics/em.md"],
    "source": "story",
}

_NAV = {
    "nav": [
        {"Home": "https://example.org/"},
        {"Vultron": "index.md"},
        {"Start": ["start/index.md", {"A": "start/a.md"}]},
        {
            "Topics": [
                "topics/index.md",
                {"Embargo": "topics/em.md"},
                "topics/untitled.md",
                {"Deeper": [{"Leaf": "topics/leaf.md"}]},
            ]
        },
    ]
}


def _suite_file(tmp_path: Path, **overrides: object) -> Path:
    data: dict[str, object] = {
        "personas": [_PERSONA],
        "tasks": [_THREAD, _LOOKUP],
    }
    data.update(overrides)
    path = tmp_path / "suite.yaml"
    path.write_text(yaml.safe_dump(data))
    return path


def _suite(tmp_path: Path) -> nu.Suite:
    return nu.load_suite(_suite_file(tmp_path))


def _docs(tmp_path: Path) -> Path:
    docs = tmp_path / "docs"
    (docs / "topics").mkdir(parents=True)
    (docs / "topics" / "untitled.md").write_text("# Titled By H1\n")
    return docs


def _nodes(tmp_path: Path) -> list[nu.NavNode]:
    return nu.nav_tree(yaml.safe_dump(_NAV), _docs(tmp_path))


class TestSuite:
    def test_committed_suite_loads_and_every_destination_exists(self):
        root = repo_root()
        suite = nu.load_suite(root / nu.SUITE_PATH)
        for task in suite.tasks:
            for page in suite.destinations(task):
                assert (root / "docs" / page).is_file(), (task.id, page)

    def test_thread_destination_is_the_personas_start_page(self, tmp_path):
        suite = _suite(tmp_path)
        assert suite.destinations(suite.tasks[0]) == ["start/a.md"]

    def test_unknown_persona_fails(self, tmp_path):
        bad = {**_LOOKUP, "persona": "nobody"}
        with pytest.raises(MetadataLoadErrors, match="unknown persona"):
            nu.load_suite(_suite_file(tmp_path, tasks=[_THREAD, bad]))

    def test_lookup_without_destination_fails(self, tmp_path):
        bad = {**_LOOKUP, "destinations": []}
        with pytest.raises(MetadataLoadErrors, match="names no destination"):
            nu.load_suite(_suite_file(tmp_path, tasks=[_THREAD, bad]))

    def test_thread_with_own_destination_fails(self, tmp_path):
        bad = {**_THREAD, "destinations": ["x.md"]}
        with pytest.raises(MetadataLoadErrors, match="declares destinations"):
            nu.load_suite(_suite_file(tmp_path, tasks=[bad, _LOOKUP]))

    def test_persona_without_thread_task_fails(self, tmp_path):
        with pytest.raises(MetadataLoadErrors, match="follow your thread"):
            nu.load_suite(_suite_file(tmp_path, tasks=[_LOOKUP]))

    def test_repeated_task_id_fails(self, tmp_path):
        with pytest.raises(MetadataLoadErrors, match="repeats task"):
            nu.load_suite(
                _suite_file(tmp_path, tasks=[_THREAD, _LOOKUP, _LOOKUP])
            )

    def test_every_fault_is_reported_at_once(self, tmp_path):
        bad = {**_LOOKUP, "persona": "nobody", "destinations": []}
        with pytest.raises(MetadataLoadErrors) as caught:
            nu.load_suite(_suite_file(tmp_path, tasks=[bad]))
        assert len(caught.value.failures) == 3

    def test_schema_fault_names_the_file(self, tmp_path):
        path = _suite_file(tmp_path, personas=[{**_PERSONA, "extra": 1}])
        with pytest.raises(MetadataLoadError, match=r"suite\.yaml"):
            nu.load_suite(path)


class TestNavTree:
    def test_group_index_becomes_the_group_link(self, tmp_path):
        topics = _nodes(tmp_path)[3]
        assert (topics.label, topics.path) == ("Topics", "topics/index.md")
        assert [c.label for c in topics.children] == [
            "Embargo",
            "Titled By H1",
            "Deeper",
        ]

    def test_group_without_index_has_no_link(self, tmp_path):
        deeper = _nodes(tmp_path)[3].children[2]
        assert deeper.path is None
        assert deeper.pages() == ["topics/leaf.md"]

    def test_render_shows_labels_never_paths_or_numbers(self, tmp_path):
        rendered = nu.render_tree(_nodes(tmp_path))
        assert rendered.splitlines()[0] == "- Home"
        assert "\n    - Leaf" in rendered and "[" not in rendered
        assert ".md" not in rendered and "example.org" not in rendered

    def test_unlabelled_missing_page_fails(self, tmp_path):
        nav = {"nav": [{"G": ["g/index.md", "g/missing.md"]}]}
        with pytest.raises(MetadataLoadError, match="does not exist"):
            nu.nav_tree(yaml.safe_dump(nav), _docs(tmp_path))

    def test_first_of_same_named_siblings_wins(self, tmp_path):
        nav = {"nav": [{"A": "x.md"}, {"A": [{"B": "y.md"}]}]}
        nodes = nu.nav_tree(yaml.safe_dump(nav), _docs(tmp_path))
        assert nu.resolve_label_path(nodes, ["a"])[0].path == "x.md"
        chain = nu.resolve_label_path(nodes, ["A", "B"])
        assert [n.label for n in chain] == ["A", "B"]

    def test_prefix_and_skipped_levels_still_resolve(self, tmp_path):
        nodes = _nodes(tmp_path)
        chain = nu.resolve_label_path(nodes, ["Vultron", "Topics", "Leaf"])
        assert [n.label for n in chain] == ["Topics", "Deeper", "Leaf"]

    def test_ancestors_pick_between_same_named_entries(self, tmp_path):
        nav = {"nav": [{"A": [{"X": "a.md"}]}, {"B": [{"X": "b.md"}]}]}
        nodes = nu.nav_tree(yaml.safe_dump(nav), _docs(tmp_path))
        assert nu.resolve_label_path(nodes, ["B", "X"])[-1].path == "b.md"
        assert nu.resolve_label_path(nodes, ["X"])[-1].path == "a.md"

    def test_hash_follows_the_nav_only(self):
        base = yaml.safe_dump(_NAV)
        same = yaml.safe_dump({**_NAV, "site_name": "Other"})
        moved = yaml.safe_dump({"nav": list(reversed(_NAV["nav"]))})
        assert nu.nav_hash(base) == nu.nav_hash(same)
        assert nu.nav_hash(base) != nu.nav_hash(moved)

    def test_prompt_carries_persona_tasks_and_tree(self, tmp_path):
        prompt = nu.tree_prompt(_suite(tmp_path), "p1", _nodes(tmp_path))
        assert "You do not know X." in prompt
        assert "T2: Find the embargo page." in prompt
        assert "- Home" in prompt


class TestScoreTree:
    def _score(self, tmp_path, answers):
        nodes = _nodes(tmp_path)
        return nodes, nu.score_tree_answers(
            _suite(tmp_path), "p1", nodes, answers
        )

    def test_outcomes(self, tmp_path):
        nodes = _nodes(tmp_path)
        answers = [
            {"task": "T1", "path": ["Start", "A"]},
            {"task": "T2", "path": ["topics", " embargo "]},
        ]
        results = nu.score_tree_answers(_suite(tmp_path), "p1", nodes, answers)
        assert [r.outcome for r in results] == [nu.Outcome.SUCCESS] * 2
        assert results[1].label_path == ["Topics", "Embargo"]

    def test_group_holding_the_destination_is_near(self, tmp_path):
        nodes = _nodes(tmp_path)
        answers = [{"task": "T2", "path": ["Topics"]}]
        results = nu.score_tree_answers(_suite(tmp_path), "p1", nodes, answers)
        assert results[1].outcome is nu.Outcome.NEAR
        assert not results[1].stalled_at_home

    def test_unanswered_and_null_are_giving_up(self, tmp_path):
        _, results = self._score(tmp_path, [{"task": "T2", "path": None}])
        assert [r.outcome for r in results] == [nu.Outcome.GAVE_UP] * 2

    def test_home_answer_is_a_stall(self, tmp_path):
        nodes = _nodes(tmp_path)
        answers = [{"task": "T2", "path": ["Vultron"]}]
        results = nu.score_tree_answers(_suite(tmp_path), "p1", nodes, answers)
        assert results[1].outcome is nu.Outcome.FAIL
        assert results[1].stalled_at_home

    def test_stray_task_fails(self, tmp_path):
        with pytest.raises(MetadataLoadError, match="not given"):
            self._score(tmp_path, [{"task": "T9", "path": ["Home"]}])

    def test_unknown_label_fails(self, tmp_path):
        with pytest.raises(
            MetadataLoadError, match="no entry is labelled 'Nope'"
        ):
            self._score(tmp_path, [{"task": "T2", "path": ["Topics", "Nope"]}])

    def test_non_list_path_fails(self, tmp_path):
        with pytest.raises(MetadataLoadError, match="list of labels or null"):
            self._score(tmp_path, [{"task": "T2", "path": "Topics"}])

    def test_empty_path_fails(self, tmp_path):
        with pytest.raises(MetadataLoadError, match="empty path"):
            self._score(tmp_path, [{"task": "T2", "path": []}])


_PAGE = """<html><head><title>{title}</title></head><body>
<header><a href="{up}index.html">Home</a><a href="{up}search.html">Search</a>
<form><a href="#x">in form</a></form></header>
<nav><a href="{up}topics/em/">Embargo</a><a href="https://x.org/">Out</a></nav>
<article><h1>{title}</h1><p>Body &amp; text.</p><script>var x;</script>
<a href="{up}topics/em/#sec">Embargo again</a></article></body></html>
"""


def _site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    (site / "topics" / "em").mkdir(parents=True)
    (site / "index.html").write_text(_PAGE.format(title="Front", up=""))
    (site / "topics" / "em" / "index.html").write_text(
        _PAGE.format(title="Embargo", up="../../")
    )
    return site


class TestWalk:
    def test_page_view_drops_search_external_and_merges_repeats(
        self, tmp_path
    ):
        view = nu.read_page(_site(tmp_path), "index.html")
        assert view.title == "Front"
        assert view.links == [
            ("Embargo / Embargo again", "topics/em/index.html")
        ]
        assert "Body & text." in view.text and "var x" not in view.text

    def test_missing_page_fails(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            nu.read_page(_site(tmp_path), "nope.html")

    def test_budget_ends_the_walk(self, tmp_path):
        walk = nu.Walk(tmp_path / "s.json")
        walk.start(_site(tmp_path), budget=1)
        assert "clicks used: 1/1" in walk.go(1)
        assert "no link 5" in walk.go(5)
        assert "out of clicks" in walk.go(1)
        assert walk.state().finished == "out-of-clicks"
        assert "over" in walk.go(1)

    def test_found_scores_against_the_built_destination(self, tmp_path):
        walk = nu.Walk(tmp_path / "s.json")
        walk.start(_site(tmp_path))
        walk.go(1)
        walk.finish("found")
        suite = _suite(tmp_path)
        result = nu.score_walk(
            suite.model_copy(
                update={
                    "tasks": [
                        suite.tasks[0],
                        suite.tasks[1].model_copy(
                            update={"destinations": ["topics/em/index.md"]}
                        ),
                    ]
                }
            ),
            "T2",
            walk.state(),
        )
        assert (result.outcome, result.clicks, result.stage) == (
            nu.Outcome.SUCCESS,
            1,
            2,
        )

    def test_found_elsewhere_fails_and_giving_up_at_home_stalls(
        self, tmp_path
    ):
        suite = _suite(tmp_path)
        site = _site(tmp_path)
        walk = nu.Walk(tmp_path / "s.json")
        walk.start(site)
        walk.finish("found")
        assert (
            nu.score_walk(suite, "T2", walk.state()).outcome is nu.Outcome.FAIL
        )
        walk.start(site)
        walk.finish("gave-up")
        result = nu.score_walk(suite, "T2", walk.state())
        assert result.outcome is nu.Outcome.GAVE_UP and result.stalled_at_home

    @pytest.mark.parametrize(
        ("docs_path", "built"),
        [
            ("index.md", "index.html"),
            ("topics/index.md", "topics/index.html"),
            ("topics/em.md", "topics/em/index.html"),
        ],
    )
    def test_site_page(self, docs_path, built):
        assert nu.site_page(docs_path) == built


def _results(
    nav: str, outcomes: dict[str, list[nu.Outcome]], stall: str = ""
) -> nu.Results:
    return nu.Results(
        nav=nav,
        nav_hash=nav,
        source="test",
        results=[
            nu.TaskResult(
                task=task,
                persona="p1",
                run=run,
                outcome=outcome,
                answer=None,
                stalled_at_home=task == stall,
            )
            for task, runs in outcomes.items()
            for run, outcome in enumerate(runs, 1)
        ],
    )


S, F = nu.Outcome.SUCCESS, nu.Outcome.FAIL


class TestTally:
    def test_no_worse_passes(self):
        verdict = nu.tally(
            _results("b", {"T1": [S], "T2": [F]}),
            _results("p", {"T1": [F], "T2": [S]}),
        )
        assert (
            verdict.passed
            and verdict.worse == ["T1"]
            and verdict.better == ["T2"]
        )

    def test_worse_fails(self):
        verdict = nu.tally(
            _results("b", {"T1": [S], "T2": [S]}),
            _results("p", {"T1": [S], "T2": [F]}),
        )
        assert not verdict.passed

    def test_stall_fails_even_when_better(self):
        verdict = nu.tally(
            _results("b", {"T1": [F]}),
            _results("p", {"T1": [S], "T2": [F]}, stall="T2"),
        )
        assert not verdict.passed and verdict.stalls == ["T2"]

    def test_repeated_runs_average(self):
        verdict = nu.tally(
            _results("b", {"T1": [S, F]}),
            _results("p", {"T1": [S, S]}),
        )
        assert verdict.better == ["T1"]


class TestCli:
    def test_score_writes_results_and_refuses_another_nav(
        self, tmp_path, capsys
    ):
        docs = _docs(tmp_path)
        config = tmp_path / "mkdocs.yml"
        config.write_text(yaml.safe_dump(_NAV))
        answers = tmp_path / "a.json"
        answers.write_text(
            json.dumps(
                {"answers": [{"task": "T2", "path": ["topics", " embargo "]}]}
            )
        )
        results = tmp_path / "r.yaml"
        argv = [
            "score",
            "--config", str(config),
            "--docs", str(docs),
            "--suite", str(_suite_file(tmp_path)),
            "--persona", "p1",
            "--answers", str(answers),
            "--results", str(results),
            "--nav", "baseline",
            "--source", "test",
        ]  # fmt: skip
        nu.main(argv)
        nu.main(argv)  # a rerun of the same run replaces, never duplicates
        saved = nu.load_results(results)
        assert len(saved.results) == 2
        assert "T2 success Topics > Embargo" in capsys.readouterr().out
        config.write_text(yaml.safe_dump({"nav": _NAV["nav"][:3]}))
        with pytest.raises(SystemExit, match="start a new results file"):
            nu.main(argv)

    def test_tally_exits_nonzero_on_fail(self, tmp_path, capsys):
        base, prop = tmp_path / "b.yaml", tmp_path / "p.yaml"
        nu.save_results(base, _results("b", {"T1": [S]}))
        nu.save_results(prop, _results("p", {"T1": [F]}))
        with pytest.raises(SystemExit):
            nu.main(
                ["tally", "--baseline", str(base), "--proposed", str(prop)]
            )
        assert "FAIL" in capsys.readouterr().out


class TestWalkPrompt:
    def test_names_each_tasks_own_session_and_the_rules(self, tmp_path):
        prompt = nu.walk_prompt(
            _suite(tmp_path), "p1", Path("/site"), Path("/s"), ["T2"]
        )
        assert "--session /s/T2.json" in prompt
        assert "There is no search" in prompt and "8 clicks" in prompt
        assert "T2: Find the embargo page." in prompt
        assert "T1:" not in prompt

    def test_unknown_task_fails(self, tmp_path):
        with pytest.raises(KeyError, match="no task"):
            nu.walk_prompt(
                _suite(tmp_path), "p1", Path("/s"), Path("/s"), ["T9"]
            )

    def test_score_walks_records_stage_2_and_refuses_unfinished(
        self, tmp_path, capsys
    ):
        suite = _suite_file(tmp_path)
        results = tmp_path / "r.yaml"
        nu.save_results(results, _results("b", {"T2": [F]}))
        sessions = tmp_path / "walks"
        sessions.mkdir()
        walk = nu.Walk(sessions / "T2.json")
        walk.start(_site(tmp_path))
        argv = [
            "score-walks",
            "--suite", str(suite),
            "--sessions", str(sessions),
            "--results", str(results),
        ]  # fmt: skip
        with pytest.raises(SystemExit, match="unfinished"):
            nu.main(argv)
        walk.finish("gave-up")
        nu.main(argv)
        nu.main(argv)
        saved = nu.load_results(results)
        assert [(r.stage, r.outcome) for r in saved.results] == [
            (1, F),
            (2, nu.Outcome.GAVE_UP),
        ]
        assert "T2 gave-up in 0 click(s)" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("current", "href", "target"),
    [
        ("index.html", "topics/em/", "topics/em/index.html"),
        ("topics/em/index.html", "../../", "index.html"),
        ("topics/em/index.html", "../x.html#a", "topics/x.html"),
        ("index.html", "#anchor", None),
        ("index.html", "mailto:x@y.org", None),
        ("index.html", "https://x.org/", None),
        ("index.html", "../outside/", None),
        ("index.html", "?q=1", None),
    ],
)
def test_resolve_href(current, href, target):
    assert nu._resolve_href(current, href) == target


class TestCliSubcommands:
    def _config(self, tmp_path):
        docs = _docs(tmp_path)
        config = tmp_path / "mkdocs.yml"
        config.write_text(yaml.safe_dump(_NAV))
        return ["--config", str(config), "--docs", str(docs)]

    def test_tree_prints_hash_and_labels(self, tmp_path, capsys):
        nu.main(["tree", *self._config(tmp_path)])
        out = capsys.readouterr().out
        assert out.startswith("nav hash: ") and "- Titled By H1" in out

    def test_prompt_prints_the_briefing(self, tmp_path, capsys):
        suite = str(_suite_file(tmp_path))
        nu.main(
            [
                "prompt",
                *self._config(tmp_path),
                "--suite",
                suite,
                "--persona",
                "p1",
            ]
        )
        assert "## Your tasks" in capsys.readouterr().out

    def test_walk_steps_and_needs_an_action(self, tmp_path, capsys):
        session = str(tmp_path / "s.json")
        site = str(_site(tmp_path))
        nu.main(["walk", "--session", session, "--start", site])
        nu.main(["walk", "--session", session, "--go", "1"])
        nu.main(["walk", "--session", session, "--found"])
        assert (
            "Recorded: found at topics/em/index.html"
            in capsys.readouterr().out
        )
        with pytest.raises(SystemExit, match="needs one of"):
            nu.main(["walk", "--session", session])

    def test_walk_prompt_and_bad_suite_exit_cleanly(self, tmp_path, capsys):
        suite = _suite_file(tmp_path)
        nu.main(
            [
                "walk-prompt",
                "--suite", str(suite),
                "--persona", "p1",
                "--site", "/site",
                "--sessions", "/s",
                "--tasks", "T1,T2",
            ]
        )  # fmt: skip
        assert "/s/T1.json" in capsys.readouterr().out
        bad = _suite_file(tmp_path, tasks=[_LOOKUP])
        with pytest.raises(SystemExit, match="follow your thread"):
            nu.main(
                [
                    "prompt",
                    *self._config(tmp_path),
                    "--suite",
                    str(bad),
                    "--persona",
                    "p1",
                ]
            )
