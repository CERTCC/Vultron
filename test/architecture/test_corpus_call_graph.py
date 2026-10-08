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

"""The text-only call graph in ``_corpus`` that ratchets use as a prefilter."""

from test.architecture import _corpus

_SOURCE = """
from m import original as alias
from n import (
    first as renamed,
    second,
)

shortcut = helper


def helper(dl):
    dl.save(thing)


class Writer:
    def run(self):
        helper(self.dl)


async def runner():
    alias()
"""


def _summaries(*, classes: bool) -> dict[str, frozenset[str]]:
    return dict(_corpus.definition_summaries(_SOURCE, classes=classes))


def test_called_names_counts_attribute_calls_and_skips_definitions() -> None:
    assert _corpus.called_names("def f(x):\n    dl.save(g(x))\n") == {
        "save",
        "g",
    }


def test_definition_summaries_span_each_top_level_definition() -> None:
    summaries = _summaries(classes=True)
    assert summaries["helper"] == {"save"}
    assert summaries["Writer"] == {"helper"}
    assert summaries["runner"] == {"alias"}


def test_definition_summaries_can_leave_classes_out() -> None:
    summaries = _summaries(classes=False)
    assert "Writer" not in summaries
    # The function before a class still ends where the class starts.
    assert summaries["helper"] == {"save"}


def test_definition_summaries_follow_import_and_assignment_aliases() -> None:
    summaries = _summaries(classes=False)
    assert summaries["alias"] == {"original"}
    assert summaries["renamed"] == {"first"}
    assert summaries["shortcut"] == {"helper"}
    assert "second" not in summaries


def test_definition_summaries_of_a_module_with_no_definitions() -> None:
    assert list(_corpus.definition_summaries("x = 1\n")) == []


def test_names_reaching_follows_helpers_across_modules() -> None:
    reached = _corpus.names_reaching(
        frozenset({"save"}),
        under=_corpus.REPO_ROOT / "vultron" / "core",
        classes=False,
    )
    # A helper that saves the case itself, and one that calls such a helper.
    assert "record_embargo_proposal_index" in reached
    assert "_seed_participant_as_signatory" in reached
