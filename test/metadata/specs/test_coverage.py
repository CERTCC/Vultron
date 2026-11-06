"""Tests for vultron.metadata.specs.coverage (SR-05-004, SR-05-005, SR-05-017,
SR-05-018)."""

import copy
import json
import sys

import pytest
import yaml

from vultron.metadata.specs.coverage import (
    CoverageState,
    ImplementerCoverageReport,
    RequirementCoverage,
    collect_marked_ids,
    compute_implementer_coverage,
    main,
    uncovered_implementer_ids,
)
from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.schema import SpecKind

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PROTOCOL_YAML = {
    "id": "CVG",
    "title": "Coverage Test Specs",
    "description": "Minimal spec file for coverage reporter tests",
    "scope": ["production"],
    "groups": [
        {
            "id": "CVG-01",
            "title": "Protocol Group",
            "specs": [
                {
                    "id": "CVG-01-001",
                    "priority": "MUST",
                    "kind": "protocol",
                    "statement": "CVG-01-001 MUST be covered",
                    "rationale": "Because testing.",
                },
                {
                    "id": "CVG-01-002",
                    "priority": "MUST",
                    "kind": "protocol",
                    "statement": "CVG-01-002 MUST also be covered",
                    "rationale": "Because testing.",
                },
                {
                    "id": "CVG-01-003",
                    "priority": "SHOULD",
                    "kind": "project",
                    "statement": "CVG-01-003 is project-kind (not counted)",
                    "rationale": "Because testing.",
                },
            ],
        }
    ],
}


@pytest.fixture
def spec_dir_with_protocol(tmp_path):
    """Spec directory containing two protocol-kind and one project-kind spec."""
    (tmp_path / "cvg_specs.yaml").write_text(yaml.dump(_PROTOCOL_YAML))
    return tmp_path


@pytest.fixture
def test_dir_with_markers(tmp_path):
    """Test directory with one marker for CVG-01-001 (one covered, one not)."""
    test_file = tmp_path / "test_sample.py"
    test_file.write_text(
        "import pytest\n"
        "\n"
        "@pytest.mark.spec('CVG-01-001')\n"
        "def test_something():\n"
        "    pass\n"
    )
    return tmp_path


@pytest.fixture
def test_dir_no_markers(tmp_path):
    """Test directory with no @pytest.mark.spec markers."""
    (tmp_path / "test_plain.py").write_text("def test_plain(): pass\n")
    return tmp_path


@pytest.fixture
def test_dir_full_coverage(tmp_path):
    """Test directory with markers for both protocol-kind specs."""
    test_file = tmp_path / "test_full.py"
    test_file.write_text(
        "import pytest\n"
        "\n"
        "@pytest.mark.spec('CVG-01-001')\n"
        "def test_one(): pass\n"
        "\n"
        "@pytest.mark.spec('CVG-01-002')\n"
        "def test_two(): pass\n"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# ImplementerCoverageReport
# ---------------------------------------------------------------------------


def _report(*states: CoverageState) -> ImplementerCoverageReport:
    return ImplementerCoverageReport(
        requirements=tuple(
            RequirementCoverage(
                id=f"CVG-01-{n:03d}",
                kind=SpecKind.PROTOCOL,
                statement="A statement.",
                state=state,
            )
            for n, state in enumerate(states, start=1)
        )
    )


_V, _X, _U = (
    CoverageState.VERIFIED,
    CoverageState.XFAIL_ONLY,
    CoverageState.UNTESTED,
)


def test_coverage_pct_zero_when_none_verified():
    assert _report(_U, _U).verified_pct == 0.0


def test_coverage_pct_100_when_all_verified():
    assert _report(_V, _V, _V, _V).verified_pct == 100.0


def test_coverage_pct_50_when_half_verified():
    assert _report(_V, _V, _U, _U).verified_pct == 50.0


def test_coverage_pct_zero_total():
    """Zero total produces 0.0 to avoid division by zero."""
    assert _report().verified_pct == 0.0


@pytest.mark.spec("SR-05-017")
def test_coverage_pct_leaves_out_xfail_only():
    """An xfail-only requirement counts in the total, never in the figure."""
    report = _report(_V, _X, _X, _U)
    assert report.verified_pct == 25.0
    assert report.summary.model_dump() == {
        "total": 4,
        "verified": 1,
        "xfail_only": 2,
        "untested": 1,
        "verified_pct": 25.0,
    }


# ---------------------------------------------------------------------------
# collect_marked_ids
# ---------------------------------------------------------------------------


def test_collect_marked_ids_finds_single_marker(test_dir_with_markers):
    ids = collect_marked_ids(test_dir_with_markers)
    assert "CVG-01-001" in ids


def test_collect_marked_ids_empty_when_no_markers(test_dir_no_markers):
    ids = collect_marked_ids(test_dir_no_markers)
    assert ids == frozenset()


def test_collect_marked_ids_skips_pycache(tmp_path):
    """Files under __pycache__ are ignored."""
    cache_dir = tmp_path / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "test_cached.py").write_text(
        "@pytest.mark.spec('SHOULD-NOT-APPEAR')\ndef f(): pass\n"
    )
    ids = collect_marked_ids(tmp_path)
    assert "SHOULD-NOT-APPEAR" not in ids


def test_collect_marked_ids_returns_frozenset(test_dir_with_markers):
    result = collect_marked_ids(test_dir_with_markers)
    assert isinstance(result, frozenset)


def test_collect_marked_ids_multiple_markers(test_dir_full_coverage):
    ids = collect_marked_ids(test_dir_full_coverage)
    assert {"CVG-01-001", "CVG-01-002"} <= ids


def test_collect_marked_ids_reads_every_id_of_a_multi_id_marker(tmp_path):
    """A marker naming several IDs covers each of them, not only the first."""
    (tmp_path / "test_multi.py").write_text(
        "@pytest.mark.spec(\"CVG-01-001\", 'CVG-01-002')\n"
        "@pytest.mark.spec(\n"
        '    "CVG-01-003",\n'
        '    "CVG-01-004",\n'
        ")\n"
        "def test_multi(): pass\n"
    )
    ids = collect_marked_ids(tmp_path)
    assert {"CVG-01-001", "CVG-01-002", "CVG-01-003", "CVG-01-004"} <= ids


def test_collect_marked_ids_reads_pytestmark_assignments(tmp_path):
    """Module- and class-level ``pytestmark`` markers count like decorators."""
    (tmp_path / "test_pytestmark.py").write_text(
        'pytestmark = [pytest.mark.spec("CVG-01-001"), '
        'pytest.mark.spec("CVG-01-002")]\n'
        "class TestX:\n"
        '    pytestmark = pytest.mark.spec("CVG-01-003")\n'
    )
    ids = collect_marked_ids(tmp_path)
    assert {"CVG-01-001", "CVG-01-002", "CVG-01-003"} <= ids


def test_collect_marked_ids_ignores_keyword_argument_values(tmp_path):
    """A keyword argument's string value is not a spec ID."""
    (tmp_path / "test_kwarg.py").write_text(
        '@pytest.mark.spec("CVG-01-001", reason="not-an-id")\n'
        "def test_k(): pass\n"
    )
    ids = collect_marked_ids(tmp_path)
    assert "CVG-01-001" in ids
    assert "not-an-id" not in ids


# ---------------------------------------------------------------------------
# compute_implementer_coverage
# ---------------------------------------------------------------------------


@pytest.mark.spec("SR-05-004")
def test_compute_returns_report(spec_dir_with_protocol, test_dir_with_markers):
    registry = load_registry(spec_dir_with_protocol)
    report = compute_implementer_coverage(registry, test_dir_with_markers)
    assert isinstance(report, ImplementerCoverageReport)


@pytest.mark.spec("SR-05-004")
def test_compute_counts_protocol_specs_only(
    spec_dir_with_protocol, test_dir_no_markers
):
    """project-kind specs are not counted in the protocol coverage total."""
    registry = load_registry(spec_dir_with_protocol)
    report = compute_implementer_coverage(registry, test_dir_no_markers)
    assert report.total == 2  # CVG-01-001 and CVG-01-002 only


@pytest.mark.spec("SR-05-004")
def test_compute_counts_foundation_specs(tmp_path, test_dir_no_markers):
    """foundation specs are guarded with protocol ones (ADR-0134)."""
    data = copy.deepcopy(_PROTOCOL_YAML)
    data["groups"][0]["specs"][2]["kind"] = "foundation"
    data["groups"][0]["specs"][2]["tags"] = ["http"]
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    (spec_dir / "cvg_specs.yaml").write_text(yaml.dump(data))
    report = compute_implementer_coverage(
        load_registry(spec_dir), test_dir_no_markers
    )
    assert report.total == 3
    assert "CVG-01-003" in report.untested


def test_compute_zero_coverage_when_no_markers(
    spec_dir_with_protocol, test_dir_no_markers
):
    registry = load_registry(spec_dir_with_protocol)
    report = compute_implementer_coverage(registry, test_dir_no_markers)
    assert report.verified == []
    assert report.verified_pct == 0.0


def test_compute_partial_coverage(
    spec_dir_with_protocol, test_dir_with_markers
):
    """One of two protocol specs is covered — 50% coverage."""
    registry = load_registry(spec_dir_with_protocol)
    report = compute_implementer_coverage(registry, test_dir_with_markers)
    assert report.verified == ["CVG-01-001"]
    assert report.total == 2
    assert report.verified_pct == 50.0


def test_compute_full_coverage(spec_dir_with_protocol, test_dir_full_coverage):
    registry = load_registry(spec_dir_with_protocol)
    report = compute_implementer_coverage(registry, test_dir_full_coverage)
    assert report.verified == ["CVG-01-001", "CVG-01-002"]
    assert report.total == 2
    assert report.verified_pct == 100.0


def test_compute_untested_lists_missing_ids(
    spec_dir_with_protocol, test_dir_with_markers
):
    """Untested list contains IDs with no markers."""
    registry = load_registry(spec_dir_with_protocol)
    report = compute_implementer_coverage(registry, test_dir_with_markers)
    assert report.untested == ["CVG-01-002"]


def test_compute_untested_is_sorted(
    spec_dir_with_protocol, test_dir_no_markers
):
    registry = load_registry(spec_dir_with_protocol)
    report = compute_implementer_coverage(registry, test_dir_no_markers)
    assert report.untested == ["CVG-01-001", "CVG-01-002"]


@pytest.mark.spec_corpus
@pytest.mark.spec("SR-05-005")
def test_compute_real_registry_has_nonzero_coverage(real_registry):
    """Smoke test: real registry + real test suite have at least one covered spec."""
    from vultron.metadata.specs.registry import find_repo_root

    repo_root = find_repo_root()
    report = compute_implementer_coverage(real_registry, repo_root / "test")
    assert report.verified, (
        "No protocol or foundation specs are covered — @pytest.mark.spec markers may "
        "have been stripped from the test suite."
    )


# ---------------------------------------------------------------------------
# main() CLI entry point
# ---------------------------------------------------------------------------


def test_main_prints_coverage_summary(
    spec_dir_with_protocol, test_dir_with_markers, monkeypatch, capsys
):
    """main() prints the coverage summary line for explicit spec_dir + test_dir."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "spec-coverage",
            str(spec_dir_with_protocol),
            str(test_dir_with_markers),
        ],
    )
    main()
    out = capsys.readouterr().out
    assert "Protocol and foundation spec coverage:" in out
    assert "/2" in out  # 2 protocol specs total


def test_main_lists_untested_ids(
    spec_dir_with_protocol, test_dir_with_markers, monkeypatch, capsys
):
    """main() lists untested IDs when coverage is partial."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "spec-coverage",
            str(spec_dir_with_protocol),
            str(test_dir_with_markers),
        ],
    )
    main()
    out = capsys.readouterr().out
    assert (
        "Untested protocol and foundation requirements (1):\n  CVG-01-002"
        in out
    )


def test_main_no_untested_section_when_fully_covered(
    spec_dir_with_protocol, test_dir_full_coverage, monkeypatch, capsys
):
    """main() omits the untested and xfail-only sections when all are verified."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "spec-coverage",
            str(spec_dir_with_protocol),
            str(test_dir_full_coverage),
        ],
    )
    main()
    out = capsys.readouterr().out
    assert (
        "Protocol and foundation spec coverage: 2/2 verified (100.0%)" in out
    )
    assert "Untested" not in out
    assert "xfail-only protocol" not in out


# ---------------------------------------------------------------------------
# Coverage states: verified, xfail-only, untested (SR-05-017)
# ---------------------------------------------------------------------------


def _protocol_specs(tmp_path, count):
    """A spec directory holding protocol requirements CVG-01-001 to -<count>."""
    data = {
        "id": "CVG",
        "title": "Coverage State Specs",
        "description": "Protocol requirements for the coverage-state tests",
        "scope": ["production"],
        "groups": [
            {
                "id": "CVG-01",
                "title": "Protocol Group",
                "specs": [
                    {
                        "id": f"CVG-01-{n:03d}",
                        "priority": "MUST",
                        "kind": "protocol",
                        "statement": f"CVG-01-{n:03d} MUST hold.",
                        "rationale": "Because testing.",
                    }
                    for n in range(1, count + 1)
                ],
            }
        ],
    }
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir(exist_ok=True)
    (spec_dir / "cvg_specs.yaml").write_text(yaml.dump(data))
    return spec_dir


def _states(tmp_path, count, **files):
    """Each requirement's state for test files *files* (name -> source)."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    for name, source in files.items():
        (test_dir / f"{name}.py").write_text(source)
    report = compute_implementer_coverage(
        load_registry(_protocol_specs(tmp_path, count)), test_dir
    )
    return {r.id: r.state for r in report.requirements}


@pytest.mark.spec("SR-05-017")
class TestCoverageStates:
    def test_a_direct_strict_xfail_alone_is_xfail_only(self, tmp_path):
        states = _states(
            tmp_path,
            1,
            test_a=(
                "import pytest\n"
                "@pytest.mark.spec('CVG-01-001')\n"
                "@pytest.mark.xfail(strict=True, reason='not built')\n"
                "def test_a(): pass\n"
            ),
        )
        assert states == {"CVG-01-001": _X}

    def test_a_module_pytestmark_xfail_holds_its_tests(self, tmp_path):
        states = _states(
            tmp_path,
            1,
            test_a=(
                "import pytest\n"
                "pytestmark = pytest.mark.xfail(strict=True, reason='r')\n"
                "@pytest.mark.spec('CVG-01-001')\n"
                "def test_a(): pass\n"
            ),
        )
        assert states == {"CVG-01-001": _X}

    def test_a_class_pytestmark_or_decorator_xfail_holds_its_tests(
        self, tmp_path
    ):
        states = _states(
            tmp_path,
            2,
            test_a=(
                "import pytest\n"
                "class TestA:\n"
                "    pytestmark = [pytest.mark.spec('CVG-01-001'),\n"
                "                  pytest.mark.xfail(strict=True, reason='r')]\n"
                "    def test_a(self): pass\n"
                "@pytest.mark.xfail(strict=True, reason='r')\n"
                "class TestB:\n"
                "    @pytest.mark.spec('CVG-01-002')\n"
                "    def test_b(self): pass\n"
            ),
        )
        assert states == {"CVG-01-001": _X, "CVG-01-002": _X}

    def test_a_parametrize_mark_xfail_holds_only_its_parameter_set(
        self, tmp_path
    ):
        states = _states(
            tmp_path,
            3,
            test_a=(
                "import pytest\n"
                "@pytest.mark.parametrize('x', [\n"
                "    pytest.param(1, marks=[pytest.mark.spec('CVG-01-001'),\n"
                "        pytest.mark.xfail(strict=True, reason='r')]),\n"
                "    pytest.param(2, marks=pytest.mark.spec('CVG-01-002')),\n"
                "])\n"
                "def test_a(x): pass\n"
                "@pytest.mark.spec('CVG-01-003')\n"
                "@pytest.mark.parametrize('y', [\n"
                "    pytest.param(1, marks=pytest.mark.xfail(strict=True)),\n"
                "])\n"
                "def test_b(y): pass\n"
            ),
        )
        assert states == {"CVG-01-001": _X, "CVG-01-002": _V, "CVG-01-003": _X}

    def test_a_passing_test_beside_an_xfail_one_is_verified(self, tmp_path):
        """AC-2: one passing marked test is enough, wherever the xfail sits."""
        states = _states(
            tmp_path,
            2,
            test_xfail=(
                "import pytest\n"
                "@pytest.mark.spec('CVG-01-001', 'CVG-01-002')\n"
                "@pytest.mark.xfail(strict=True, reason='r')\n"
                "def test_a(): pass\n"
            ),
            test_runs=(
                "import pytest\n"
                "@pytest.mark.spec('CVG-01-001')\n"
                "def test_b(): pass\n"
                "@pytest.mark.spec('CVG-01-002')\n"
                "@pytest.mark.parametrize('x', [\n"
                "    pytest.param(1, marks=pytest.mark.xfail(strict=True)),\n"
                "    2,\n"
                "])\n"
                "def test_c(x): pass\n"
            ),
        )
        assert states == {"CVG-01-001": _V, "CVG-01-002": _V}

    def test_a_marker_the_reader_cannot_place_stays_verified(self, tmp_path):
        """A marker outside a module- or class-level test keeps its old count."""
        states = _states(
            tmp_path,
            1,
            test_a=(
                "import pytest\n"
                "def make():\n"
                "    @pytest.mark.spec('CVG-01-001')\n"
                "    def test_inner(): pass\n"
                "    return test_inner\n"
            ),
        )
        assert states == {"CVG-01-001": _V}

    def test_an_unplaced_marker_beside_a_placed_xfail_is_verified(
        self, tmp_path
    ):
        """A passing test the reader cannot place still verifies."""
        states = _states(
            tmp_path,
            1,
            test_a=(
                "import pytest\n"
                "@pytest.mark.spec('CVG-01-001')\n"
                "@pytest.mark.xfail(strict=True, reason='r')\n"
                "def test_gap(): pass\n"
                "def make():\n"
                "    @pytest.mark.spec('CVG-01-001')\n"
                "    def test_inner(): pass\n"
                "    return test_inner\n"
            ),
        )
        assert states == {"CVG-01-001": _V}

    @pytest.mark.spec("SR-05-005")
    def test_the_growth_guard_set_is_the_untested_set(self, tmp_path):
        """An xfail-only requirement has a marker, so the guard ignores it."""
        source = (
            "import pytest\n"
            "@pytest.mark.spec('CVG-01-001')\n"
            "@pytest.mark.xfail(strict=True, reason='r')\n"
            "def test_a(): pass\n"
            "@pytest.mark.spec('CVG-01-002')\n"
            "def test_b(): pass\n"
        )
        states = _states(tmp_path, 3, test_a=source)
        assert states == {"CVG-01-001": _X, "CVG-01-002": _V, "CVG-01-003": _U}
        assert uncovered_implementer_ids(tmp_path) == {"CVG-01-003"}
        assert uncovered_implementer_ids(tmp_path, test_sources=[source]) == {
            "CVG-01-003"
        }


# ---------------------------------------------------------------------------
# JSON output (SR-05-018)
# ---------------------------------------------------------------------------

_JSON_TESTS = (
    "import pytest\n"
    "_TRACKED = 'Tracked by #4242 (source #4241).'\n"
    "@pytest.mark.spec('CVG-01-001')\n"
    "@pytest.mark.xfail(strict=True, reason=f'CVG-01-001: not built. {_TRACKED}')\n"
    "def test_gap(): pass\n"
    "class TestBuilt:\n"
    "    @pytest.mark.spec('CVG-01-002')\n"
    "    def test_built(self): pass\n"
    "    @pytest.mark.spec('CVG-01-002')\n"
    "    @pytest.mark.xfail(strict=True, reason='CVG-01-002: one edge. See #7.')\n"
    "    def test_edge(self): pass\n"
)


@pytest.mark.spec("SR-05-018")
class TestJsonOutput:
    def _run(self, tmp_path, monkeypatch, out):
        spec_dir = _protocol_specs(tmp_path, 3)
        test_dir = tmp_path / "test"
        test_dir.mkdir(exist_ok=True)
        (test_dir / "test_json.py").write_text(_JSON_TESTS)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "spec-coverage",
                str(spec_dir),
                str(test_dir),
                "--json",
                str(out),
            ],
        )
        main()
        return out.read_text(encoding="utf-8")

    def test_each_requirement_has_its_state_and_xfail_reasons(
        self, tmp_path, monkeypatch, capsys
    ):
        doc = json.loads(
            self._run(tmp_path, monkeypatch, tmp_path / "coverage.json")
        )
        by_id = {r["id"]: r for r in doc["requirements"]}

        assert by_id["CVG-01-001"] == {
            "id": "CVG-01-001",
            "kind": "protocol",
            "statement": "CVG-01-001 MUST hold.",
            "state": "xfail_only",
            "xfail_tests": [
                {
                    "test": "test/test_json.py::test_gap",
                    "reason": "CVG-01-001: not built. "
                    "Tracked by #4242 (source #4241).",
                    "issues": [4241, 4242],
                }
            ],
        }
        assert by_id["CVG-01-002"]["state"] == "verified"
        assert by_id["CVG-01-002"]["xfail_tests"] == [
            {
                "test": "test/test_json.py::TestBuilt::test_edge",
                "reason": "CVG-01-002: one edge. See #7.",
                "issues": [7],
            }
        ]
        assert by_id["CVG-01-003"]["state"] == "untested"
        assert by_id["CVG-01-003"]["xfail_tests"] == []
        assert doc["summary"] == {
            "total": 3,
            "verified": 1,
            "xfail_only": 1,
            "untested": 1,
            "verified_pct": 100.0 / 3,
        }
        out = capsys.readouterr().out
        assert "1/3 verified (33.3%)" in out
        assert (
            "xfail-only protocol and foundation requirements (1):\n"
            "  CVG-01-001\n"
            "      CVG-01-001: not built. Tracked by #4242 (source #4241).\n"
        ) in out

    def test_the_same_tree_writes_the_same_bytes(self, tmp_path, monkeypatch):
        first = self._run(tmp_path, monkeypatch, tmp_path / "a.json")
        assert first == self._run(tmp_path, monkeypatch, tmp_path / "b.json")

    def test_xfails_sort_by_test_then_reason_with_none_first(
        self, tmp_path, monkeypatch, capsys
    ):
        spec_dir = _protocol_specs(tmp_path, 1)
        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "test_order.py").write_text(
            "import pytest\n"
            "@pytest.mark.spec('CVG-01-001')\n"
            "@pytest.mark.xfail(strict=True, reason='')\n"
            "@pytest.mark.xfail(strict=True, reason='b')\n"
            "@pytest.mark.xfail(strict=True)\n"
            "def test_a(): pass\n"
        )
        out = tmp_path / "order.json"
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "spec-coverage",
                str(spec_dir),
                str(test_dir),
                "--json",
                str(out),
            ],
        )
        main()
        doc = json.loads(out.read_text(encoding="utf-8"))
        reasons = [t["reason"] for t in doc["requirements"][0]["xfail_tests"]]
        assert reasons == [None, "", "b"]
        assert "      (no reason)\n" in capsys.readouterr().out

    def test_without_json_no_file_is_written(self, tmp_path, monkeypatch):
        spec_dir = _protocol_specs(tmp_path, 1)
        monkeypatch.setattr(
            sys, "argv", ["spec-coverage", str(spec_dir), str(tmp_path)]
        )
        main()
        assert not list(tmp_path.glob("*.json"))
