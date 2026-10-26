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
"""The suite loader: personas, tasks and their cross-checks."""

from __future__ import annotations

import pytest

from test.metadata.docs.nav_usability._fixtures import (
    _LOOKUP,
    _PERSONA,
    _THREAD,
    _suite,
    _suite_file,
)
from vultron.metadata.base import repo_root
from vultron.metadata.docs import nav_usability as nu
from vultron.metadata.file_loading import MetadataLoadError, MetadataLoadErrors


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
