"""Tests for vultron.metadata.specs.marked_tests (SR-05-017)."""

import ast
import uuid

import pytest

from vultron.metadata.specs import marked_tests
from vultron.metadata.specs.marked_tests import (
    MarkedCase,
    issue_refs,
    marked_cases_in,
    read_marked_file,
)

pytestmark = pytest.mark.spec("SR-05-017")


def _cases(source: str) -> list[MarkedCase]:
    return marked_cases_in("t.py", "import pytest\n" + source)


def _view(
    source: str,
) -> set[tuple[str, frozenset[str], tuple[str | None, ...]]]:
    return {(c.test, c.spec_ids, c.xfail_reasons) for c in _cases(source)}


def test_a_file_without_a_spec_marker_has_no_cases():
    assert (
        _cases("@pytest.mark.xfail(strict=True)\ndef test_a(): pass\n") == []
    )


def test_a_decorated_test_is_one_case():
    assert _view(
        "@pytest.mark.spec('A', 'B', reason='kw')\ndef test_a(): pass\n"
    ) == {("t.py::test_a", frozenset({"A", "B"}), ())}


def test_marks_from_module_class_and_function_combine():
    view = _view(
        "pytestmark = [pytest.mark.spec('M')]\n"
        "@pytest.mark.xfail(strict=True, reason='class')\n"
        "class TestOuter:\n"
        "    pytestmark = pytest.mark.spec('C')\n"
        "    class TestInner:\n"
        "        @pytest.mark.spec('F')\n"
        "        def test_f(self): pass\n"
        "def test_plain(): pass\n"
    )
    assert view == {
        (
            "t.py::TestOuter::TestInner::test_f",
            frozenset({"M", "C", "F"}),
            ("class",),
        ),
        ("t.py::test_plain", frozenset({"M"}), ()),
    }


def test_a_bare_xfail_counts_with_no_reason():
    assert _view(
        "@pytest.mark.spec('A')\n@pytest.mark.xfail\ndef test_a(): pass\n"
    ) == {("t.py::test_a", frozenset({"A"}), (None,))}


def test_parameter_sets_are_separate_cases():
    view = _view(
        "@pytest.mark.spec('F')\n"
        "@pytest.mark.parametrize('x', [\n"
        "    pytest.param(1, marks=(pytest.mark.spec('P'),\n"
        "        pytest.mark.xfail(strict=True, reason='p'))),\n"
        "    2,\n"
        "    3,\n"
        "])\n"
        "def test_a(x): pass\n"
    )
    assert view == {
        ("t.py::test_a", frozenset({"F", "P"}), ("p",)),
        ("t.py::test_a", frozenset({"F"}), ()),
    }


def test_two_parametrize_decorators_make_their_cross_product():
    view = _view(
        "@pytest.mark.parametrize('x', [\n"
        "    pytest.param(1, marks=pytest.mark.spec('A')),\n"
        "])\n"
        "@pytest.mark.parametrize('y', argvalues=[\n"
        "    pytest.param(1, marks=pytest.mark.xfail(strict=True, reason='y')),\n"
        "    pytest.param(2, marks=pytest.mark.spec('B')),\n"
        "])\n"
        "def test_a(x, y): pass\n"
    )
    assert view == {
        ("t.py::test_a", frozenset({"A"}), ("y",)),
        ("t.py::test_a", frozenset({"A", "B"}), ()),
    }


def test_a_comprehension_yields_both_branches_of_a_conditional():
    view = _view(
        "@pytest.mark.spec('A')\n"
        "@pytest.mark.parametrize('x', [\n"
        "    pytest.param(v, marks=[pytest.mark.xfail(strict=True, reason='c')])\n"
        "    if v in GAPS else pytest.param(v)\n"
        "    for v in VALUES\n"
        "])\n"
        "def test_a(x): pass\n"
    )
    assert view == {
        ("t.py::test_a", frozenset({"A"}), ("c",)),
        ("t.py::test_a", frozenset({"A"}), ()),
    }


def test_a_comprehension_of_xfail_params_is_xfail_only():
    view = _view(
        "@pytest.mark.spec('A')\n"
        "@pytest.mark.parametrize('x', [\n"
        "    pytest.param(v, marks=pytest.mark.xfail(strict=True, reason=r))\n"
        "    for v, r in GAPS.items()\n"
        "])\n"
        "def test_a(x): pass\n"
    )
    assert view == {("t.py::test_a", frozenset({"A"}), (None,))}


def test_an_unreadable_argument_list_counts_as_one_unmarked_set():
    view = _view(
        "@pytest.mark.spec('A')\n"
        "@pytest.mark.parametrize('x', _params())\n"
        "def test_a(x): pass\n"
    )
    assert view == {("t.py::test_a", frozenset({"A"}), ())}


def test_a_reason_is_resolved_from_module_string_constants():
    view = _view(
        "_ISSUE = 'Tracked by #12.'\n"
        "_BOTH: str = 'A: ' + _ISSUE\n"
        "@pytest.mark.spec('A')\n"
        "@pytest.mark.xfail(strict=True, reason=f'A: gap. {_ISSUE}')\n"
        "@pytest.mark.xfail(strict=True, reason=_BOTH)\n"
        "@pytest.mark.xfail(strict=True, reason=f'{_ISSUE!r}')\n"
        "@pytest.mark.xfail(strict=True, reason=REASONS['A'])\n"
        "def test_a(): pass\n"
    )
    assert view == {
        (
            "t.py::test_a",
            frozenset({"A"}),
            ("A: gap. Tracked by #12.", "A: Tracked by #12.", None, None),
        )
    }


def test_a_marked_case_is_xfail_only_with_a_reason_entry():
    assert MarkedCase("t", frozenset({"A"}), (None,)).is_xfail
    assert not MarkedCase("t", frozenset({"A"}), ()).is_xfail


def test_issue_refs_are_sorted_and_unique():
    assert issue_refs("Tracked by #42 (source #7, #42).") == (7, 42)
    assert issue_refs("no issue") == ()
    assert issue_refs(None) == ()


def test_a_file_that_does_not_parse_raises_naming_it():
    with pytest.raises(SyntaxError) as raised:
        marked_cases_in("broken.py", "@pytest.mark.spec('A')\ndef (:\n")
    assert raised.value.filename == "broken.py"


def test_a_conditional_xfail_counts_as_holding():
    """The report errs toward listing a gap: a condition is not evaluated."""
    assert _view(
        "@pytest.mark.spec('A')\n"
        "@pytest.mark.xfail(sys.platform == 'win32', reason='w', strict=True)\n"
        "def test_a(): pass\n"
    ) == {("t.py::test_a", frozenset({"A"}), ("w",))}


def test_an_unconditional_skip_holds_like_an_xfail():
    view = _view(
        "@pytest.mark.spec('A')\n"
        "@pytest.mark.skip(reason='later')\n"
        "def test_a(): pass\n"
        "@pytest.mark.spec('B')\n"
        "@pytest.mark.skip('positional')\n"
        "def test_b(): pass\n"
        "@pytest.mark.spec('C')\n"
        "@pytest.mark.skip\n"
        "def test_c(): pass\n"
    )
    assert view == {
        ("t.py::test_a", frozenset({"A"}), ("skip: later",)),
        ("t.py::test_b", frozenset({"B"}), ("skip: positional",)),
        ("t.py::test_c", frozenset({"C"}), ("skip:",)),
    }


def test_an_empty_parameter_list_holds_like_a_skip():
    assert _view(
        "@pytest.mark.spec('A')\n"
        "@pytest.mark.parametrize('x', [])\n"
        "def test_a(x): pass\n"
    ) == {
        ("t.py::test_a", frozenset({"A"}), ("skip: got empty parameter set",))
    }


def test_only_the_last_pytestmark_counts_and_its_parametrize_is_an_axis():
    view = _view(
        "pytestmark = pytest.mark.xfail(strict=True, reason='overwritten')\n"
        "pytestmark = [pytest.mark.spec('M'), pytest.mark.parametrize('x', [\n"
        "    pytest.param(1, marks=pytest.mark.xfail(strict=True, reason='p')),\n"
        "    2,\n"
        "])]\n"
        "def test_a(x): pass\n"
    )
    assert view == {
        ("t.py::test_a", frozenset({"M"}), ("p",)),
        ("t.py::test_a", frozenset({"M"}), ()),
    }


def test_literal_param_ids_name_the_case():
    view = _view(
        "@pytest.mark.parametrize('x', [\n"
        "    pytest.param(1, id='one', marks=pytest.mark.spec('A')),\n"
        "])\n"
        "@pytest.mark.parametrize('y', [\n"
        "    pytest.param(1, id='gap', marks=pytest.mark.xfail(strict=True)),\n"
        "    pytest.param(2, marks=pytest.mark.spec('B')),\n"
        "])\n"
        "def test_a(x, y): pass\n"
    )
    assert view == {
        ("t.py::test_a[gap-one]", frozenset({"A"}), (None,)),
        ("t.py::test_a", frozenset({"A", "B"}), ()),
    }


def test_param_ids_join_from_the_closest_parametrize_outward():
    view = _view(
        "pytestmark = pytest.mark.parametrize('m', [pytest.param(1, id='M')])\n"
        "class TestC:\n"
        "    pytestmark = pytest.mark.parametrize(\n"
        "        'c', [pytest.param(1, id='C')])\n"
        "    @pytest.mark.spec('A')\n"
        "    @pytest.mark.parametrize('a', [pytest.param(1, id='A')])\n"
        "    @pytest.mark.parametrize('b', [pytest.param(1, id='B')])\n"
        "    def test_f(self, m, c, a, b): pass\n"
    )
    assert view == {("t.py::TestC::test_f[B-A-C-M]", frozenset({"A"}), ())}


def test_async_tests_set_marks_and_set_or_generator_arguments_are_read():
    view = _view(
        "@pytest.mark.spec('A')\n"
        "@pytest.mark.parametrize('x', {\n"
        "    pytest.param(v, marks={pytest.mark.xfail(strict=True, reason='s')})\n"
        "    for v in VALUES\n"
        "})\n"
        "async def test_a(x): pass\n"
        "@pytest.mark.spec('B')\n"
        "@pytest.mark.parametrize('x', (\n"
        "    pytest.param(v, marks=pytest.mark.xfail(strict=True, reason='g'))\n"
        "    for v in VALUES\n"
        "))\n"
        "def test_b(x): pass\n"
    )
    assert view == {
        ("t.py::test_a", frozenset({"A"}), ("s",)),
        ("t.py::test_b", frozenset({"B"}), ("g",)),
    }


def test_a_spec_call_the_reader_cannot_place_gets_an_unheld_case():
    view = _view(
        "@pytest.mark.spec('A')\n"
        "@pytest.mark.xfail(strict=True, reason='r')\n"
        "def test_a(): pass\n"
        "def make():\n"
        "    @pytest.mark.spec('A', 'B')\n"
        "    def test_inner(): pass\n"
        "    return test_inner\n"
    )
    assert view == {
        ("t.py::test_a", frozenset({"A"}), ("r",)),
        ("t.py", frozenset({"A", "B"}), ()),
    }


def test_reading_a_file_walks_its_spec_calls_once(monkeypatch):
    """The file's IDs and its unplaced IDs come from one walk (#5880)."""
    walks: list[object] = []
    real_walk = marked_tests._spec_calls

    def counting_walk(tree, source):
        walks.append(tree)
        return real_walk(tree, source)

    monkeypatch.setattr(marked_tests, "_spec_calls", counting_walk)
    source = (
        f"# {uuid.uuid4()}\nimport pytest\n"
        "@pytest.mark.spec('A')\ndef test_a(): pass\n"
        "def _factory():\n    return pytest.mark.spec('B')\n"
    )
    marked = read_marked_file("t.py", source)
    assert marked.spec_ids == {"A", "B"}
    assert ("t.py", frozenset({"B"}), ()) in {
        (c.test, c.spec_ids, c.xfail_reasons) for c in marked.cases
    }
    assert len(walks) == 1


def test_rereading_an_unchanged_file_parses_it_once(monkeypatch):
    """Checks in one run that read the test tree share each parse (#5880)."""
    parses: list[str] = []
    real_parse = ast.parse

    def counting_parse(source, *args, **kwargs):
        parses.append(source)
        return real_parse(source, *args, **kwargs)

    monkeypatch.setattr(marked_tests.ast, "parse", counting_parse)
    source = (
        f"# {uuid.uuid4()}\nimport pytest\n"
        "@pytest.mark.spec('A')\ndef test_a(): pass\n"
    )
    first = read_marked_file("t.py", source)
    assert read_marked_file("t.py", source) == first
    assert len(parses) == 1
    edited = source.replace("'A'", "'C'")
    assert read_marked_file("t.py", edited).spec_ids == {"C"}
