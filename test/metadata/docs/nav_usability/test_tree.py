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
"""Stage 1: the label tree, label-path resolution and scoring."""

from __future__ import annotations

import pytest
import yaml

from test.metadata.docs.nav_usability._fixtures import (
    _NAV,
    _docs,
    _nodes,
    _suite,
)
from vultron.metadata.docs import nav_usability as nu
from vultron.metadata.file_loading import MetadataLoadError


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
