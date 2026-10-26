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
"""Shared builders for the nav usability test harness tests."""

from __future__ import annotations

from pathlib import Path

import yaml

from vultron.metadata.docs import nav_usability as nu

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
