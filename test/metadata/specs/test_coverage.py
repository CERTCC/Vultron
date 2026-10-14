"""Tests for vultron.metadata.specs.coverage (SR-05-004, SR-05-005)."""

import copy
import sys

import pytest
import yaml

from vultron.metadata.specs.coverage import (
    ImplementerCoverageReport,
    collect_marked_ids,
    compute_implementer_coverage,
    main,
)
from vultron.metadata.specs.registry import load_registry

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
                },
                {
                    "id": "CVG-01-002",
                    "priority": "MUST",
                    "kind": "protocol",
                    "statement": "CVG-01-002 MUST also be covered",
                },
                {
                    "id": "CVG-01-003",
                    "priority": "SHOULD",
                    "kind": "project",
                    "statement": "CVG-01-003 is project-kind (not counted)",
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


def test_coverage_pct_zero_when_none_covered():
    report = ImplementerCoverageReport(total=10, covered_count=0)
    assert report.covered_pct == 0.0


def test_coverage_pct_100_when_all_covered():
    report = ImplementerCoverageReport(total=4, covered_count=4)
    assert report.covered_pct == 100.0


def test_coverage_pct_50_when_half_covered():
    report = ImplementerCoverageReport(total=4, covered_count=2)
    assert report.covered_pct == 50.0


def test_coverage_pct_zero_total():
    """Zero total produces 0.0 to avoid division by zero."""
    report = ImplementerCoverageReport(total=0, covered_count=0)
    assert report.covered_pct == 0.0


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
    assert "CVG-01-003" in report.uncovered


def test_compute_zero_coverage_when_no_markers(
    spec_dir_with_protocol, test_dir_no_markers
):
    registry = load_registry(spec_dir_with_protocol)
    report = compute_implementer_coverage(registry, test_dir_no_markers)
    assert report.covered_count == 0
    assert report.covered_pct == 0.0


def test_compute_partial_coverage(
    spec_dir_with_protocol, test_dir_with_markers
):
    """One of two protocol specs is covered — 50% coverage."""
    registry = load_registry(spec_dir_with_protocol)
    report = compute_implementer_coverage(registry, test_dir_with_markers)
    assert report.covered_count == 1
    assert report.total == 2
    assert report.covered_pct == 50.0


def test_compute_full_coverage(spec_dir_with_protocol, test_dir_full_coverage):
    registry = load_registry(spec_dir_with_protocol)
    report = compute_implementer_coverage(registry, test_dir_full_coverage)
    assert report.covered_count == 2
    assert report.total == 2
    assert report.covered_pct == 100.0


def test_compute_uncovered_lists_missing_ids(
    spec_dir_with_protocol, test_dir_with_markers
):
    """Uncovered list contains IDs with no markers."""
    registry = load_registry(spec_dir_with_protocol)
    report = compute_implementer_coverage(registry, test_dir_with_markers)
    assert "CVG-01-002" in report.uncovered
    assert "CVG-01-001" not in report.uncovered


def test_compute_uncovered_is_sorted(
    spec_dir_with_protocol, test_dir_no_markers
):
    registry = load_registry(spec_dir_with_protocol)
    report = compute_implementer_coverage(registry, test_dir_no_markers)
    assert report.uncovered == sorted(report.uncovered)


@pytest.mark.spec_corpus
@pytest.mark.spec("SR-05-005")
def test_compute_real_registry_has_nonzero_coverage(real_registry):
    """Smoke test: real registry + real test suite have at least one covered spec."""
    from vultron.metadata.specs.registry import find_repo_root

    repo_root = find_repo_root()
    report = compute_implementer_coverage(real_registry, repo_root / "test")
    assert report.covered_count > 0, (
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


def test_main_lists_uncovered_ids(
    spec_dir_with_protocol, test_dir_with_markers, monkeypatch, capsys
):
    """main() lists uncovered IDs when coverage is partial."""
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
    assert "CVG-01-002" in out  # the uncovered ID


def test_main_no_uncovered_section_when_fully_covered(
    spec_dir_with_protocol, test_dir_full_coverage, monkeypatch, capsys
):
    """main() omits the uncovered section when all specs are covered."""
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
    assert "Protocol and foundation spec coverage:" in out
    assert "Uncovered" not in out
