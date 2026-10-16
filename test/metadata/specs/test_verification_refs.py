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
"""Tests for :mod:`vultron.metadata.specs.verification_refs` (MS-10-010/011).

Synthetic spec IDs (``TST-``) are allowed here: SR-04-008 exempts
``test/metadata/specs/``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from test.metadata.specs._helpers import write_yaml
from test.metadata.specs.conftest import spec_file_data
from vultron.metadata.specs.lint import lint
from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.verification_refs import (
    SuiteIndex,
    changed_requirement_ids,
    check_test_refs,
    clause_refs,
    index_module,
    named_tests_lack_marker,
    requirement_fingerprints,
    unmarked_named_test_ids,
    unresolved_test_refs,
)

_MODULE_A = """
import pytest


def test_alpha():
    pass


@pytest.mark.spec("TST-01-001")
class TestGroup:
    def test_beta(self):
        pass

    class TestInner:
        def test_gamma(self):
            pass

    def helper(self):
        def test_nested_in_a_function():
            pass
"""

_MODULE_B = """
def test_only_in_b():
    pass
"""


def _tree(root: Path) -> SuiteIndex:
    files = {
        "test/pkg/test_a.py": _MODULE_A,
        "test/other/test_b.py": _MODULE_B,
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return SuiteIndex.build(root)


def _spec(root: Path, verification: str, kind: str = "project"):
    specs = root / "specs"
    specs.mkdir(exist_ok=True)
    write_yaml(
        specs,
        spec_file_data(
            [("TST-01-001", "MUST", kind, {"verification": verification})]
        ),
    )
    return load_registry(specs).all_specs["TST-01-001"]


class TestIndexModule:
    def test_nodes_follow_the_class_chain(self):
        module = index_module(Path("test_a.py"), _MODULE_A)
        assert {
            "test_alpha",
            "TestGroup",
            "TestGroup::test_beta",
            "TestGroup::TestInner",
            "TestGroup::TestInner::test_gamma",
            "TestGroup::helper",
        } <= module.nodes

    def test_a_def_inside_a_function_is_a_name_not_a_node(self):
        module = index_module(Path("test_a.py"), _MODULE_A)
        assert "test_nested_in_a_function" in module.names
        assert not any(
            n.endswith("test_nested_in_a_function") for n in module.nodes
        )

    def test_the_module_stem_is_a_name(self):
        assert "test_a" in index_module(Path("test_a.py"), _MODULE_A).names


class TestClauseRefs:
    def test_reads_files_nodes_dirs_and_names(self, tmp_path):
        index = _tree(tmp_path)
        refs = clause_refs(
            "`test/pkg/test_a.py::TestGroup::test_beta` and `test_only_in_b` "
            "in `test/other/`; `test_a.py` too, and `test_prefix_*`.",
            index,
        )
        assert refs.files == ("test/pkg/test_a.py",)
        assert refs.nodes == (("test/pkg/test_a.py", "TestGroup::test_beta"),)
        assert refs.dirs == ("test/other/",)
        assert refs.names == ("test_only_in_b", "test_prefix_*")

    def test_a_file_path_is_not_a_directory_reference(self, tmp_path):
        refs = clause_refs("`test/pkg/test_a.py`", _tree(tmp_path))
        assert refs.dirs == ()


@pytest.mark.spec("MS-10-010")
class TestUnresolvedTestRefs:
    def _problems(self, tmp_path: Path, verification: str) -> list[str]:
        index = _tree(tmp_path)
        spec = _spec(tmp_path, verification)
        return unresolved_test_refs("TST-01-001", spec, index)

    def test_a_resolved_name_passes(self, tmp_path):
        assert self._problems(tmp_path, "`test_alpha` checks it.") == []

    def test_an_unresolved_name_is_reported(self, tmp_path):
        (problem,) = self._problems(tmp_path, "`test_missing` checks it.")
        assert "`test_missing`" in problem
        assert "no test file defines it" in problem

    def test_a_name_in_a_module_other_than_the_one_named_is_reported(
        self, tmp_path
    ):
        (problem,) = self._problems(
            tmp_path, "`test_only_in_b` in `test/pkg/test_a.py` checks it."
        )
        assert "defined in test/other/test_b.py" in problem

    def test_a_name_under_a_named_directory_passes(self, tmp_path):
        verification = "`test_only_in_b` in `test/other/` checks it."
        assert self._problems(tmp_path, verification) == []

    def test_a_name_resolves_against_any_named_file(self, tmp_path):
        verification = (
            "`test_alpha` and `test_only_in_b` in `test/pkg/test_a.py` and "
            "`test/other/test_b.py`."
        )
        assert self._problems(tmp_path, verification) == []

    def test_a_full_node_path_passes(self, tmp_path):
        verification = "`test/pkg/test_a.py::TestGroup::TestInner::test_gamma`"
        assert self._problems(tmp_path, verification) == []

    def test_a_method_named_without_its_class_is_reported(self, tmp_path):
        (problem,) = self._problems(
            tmp_path, "`test/pkg/test_a.py::test_beta` checks it."
        )
        assert "`test_beta` is not a test in test/pkg/test_a.py" in problem

    def test_a_parametrized_node_resolves_without_its_id(self, tmp_path):
        verification = "`test/pkg/test_a.py::test_alpha[case-1]`"
        assert self._problems(tmp_path, verification) == []

    def test_a_node_in_a_missing_file_is_left_to_ms_15_001(self, tmp_path):
        assert self._problems(tmp_path, "`test/pkg/test_gone.py::x`") == []

    def test_a_prefix_pattern_resolves_on_any_match(self, tmp_path):
        assert self._problems(tmp_path, "the `test_alp*` tests") == []
        (problem,) = self._problems(tmp_path, "the `test_zzz*` tests")
        assert "`test_zzz*`" in problem

    def test_a_test_file_name_is_not_a_test_name(self, tmp_path):
        assert self._problems(tmp_path, "see test_a.py") == []

    def test_the_corpus_check_reports_through_lint(self, tmp_path):
        _tree(tmp_path)
        _spec(tmp_path, "`test_missing` checks it.")
        assert check_test_refs(
            load_registry(tmp_path / "specs"), tmp_path
        ) == [
            "TST-01-001: verification names `test_missing`, but no test file "
            "defines it. Point at the test that exists, or write the missing "
            "test (MS-10-010)."
        ]
        assert lint(tmp_path / "specs", adr_dir=tmp_path / "no-adrs") == 1
        _spec(tmp_path, "`test_alpha` checks it.")
        assert lint(tmp_path / "specs", adr_dir=tmp_path / "no-adrs") == 0


@pytest.mark.spec("MS-10-011")
class TestNamedTestsLackMarker:
    def test_a_marked_named_file_passes(self, tmp_path):
        index = _tree(tmp_path)
        spec = _spec(tmp_path, "`test/pkg/test_a.py` checks it.", "protocol")
        assert not named_tests_lack_marker("TST-01-001", spec, index)

    def test_an_unmarked_named_file_fails(self, tmp_path):
        index = _tree(tmp_path)
        spec = _spec(tmp_path, "`test/other/test_b.py` checks it.", "protocol")
        assert named_tests_lack_marker("TST-01-001", spec, index)

    def test_one_marked_file_among_several_is_enough(self, tmp_path):
        index = _tree(tmp_path)
        verification = "`test/other/test_b.py` and `test/pkg/test_a.py`"
        spec = _spec(tmp_path, verification, "foundation")
        assert not named_tests_lack_marker("TST-01-001", spec, index)

    def test_a_clause_naming_no_test_file_is_not_held(self, tmp_path):
        index = _tree(tmp_path)
        spec = _spec(tmp_path, "Inspection confirms it.", "protocol")
        assert not named_tests_lack_marker("TST-01-001", spec, index)

    def test_other_kinds_are_not_held(self, tmp_path):
        index = _tree(tmp_path)
        spec = _spec(tmp_path, "`test/other/test_b.py` checks it.", "project")
        assert not named_tests_lack_marker("TST-01-001", spec, index)

    def test_the_extractor_lists_the_failing_ids(self, tmp_path):
        _tree(tmp_path)
        _spec(tmp_path, "`test/other/test_b.py` checks it.", "protocol")
        assert unmarked_named_test_ids(tmp_path) == {"TST-01-001"}


class TestChangedRequirementIds:
    def test_new_and_changed_ids_are_listed(self):
        base = {"A": "1", "B": "2", "C": "3"}
        head = {"A": "1", "B": "changed", "D": "new"}
        assert changed_requirement_ids(base, head) == {"B", "D"}

    def test_fingerprints_change_with_any_field(self, tmp_path):
        _spec(tmp_path, "`test_alpha` checks it.")
        before = requirement_fingerprints(tmp_path)
        _spec(tmp_path, "`test_alpha` checks it, again.")
        after = requirement_fingerprints(tmp_path)
        assert changed_requirement_ids(before, after) == {"TST-01-001"}
