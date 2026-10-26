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
"""Stage 2: the page reader, walk sessions and the walk briefing."""

from __future__ import annotations

from pathlib import Path

import pytest

from test.metadata.docs.nav_usability._fixtures import (
    F,
    _results,
    _site,
    _suite,
    _suite_file,
)
from vultron.metadata.docs import nav_usability as nu
from vultron.metadata.docs.nav_usability.walk import _resolve_href
from vultron.metadata.file_loading import MetadataLoadError


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
    assert _resolve_href(current, href) == target


def test_score_walk_refuses_an_unknown_task(tmp_path):
    state = nu.WalkState(site="site", history=["index.html"], finished="found")
    with pytest.raises(MetadataLoadError, match="does not have"):
        nu.score_walk(_suite(tmp_path), "T9", state)
