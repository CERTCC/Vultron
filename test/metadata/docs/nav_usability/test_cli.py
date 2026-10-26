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
"""The nav-usability command line."""

from __future__ import annotations

import json

import pytest
import yaml

from test.metadata.docs.nav_usability._fixtures import (
    _LOOKUP,
    _NAV,
    F,
    S,
    _docs,
    _results,
    _site,
    _suite_file,
)
from vultron.metadata.docs import nav_usability as nu


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
