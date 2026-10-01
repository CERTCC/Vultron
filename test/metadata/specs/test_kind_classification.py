"""Tests for vultron.metadata.specs.kind_classification (MS-12-006/007/008).

The lint-path behaviour — exit code, story-bearing exemption, suppression — is
covered in ``test_lint.py``. This module pins the detector itself: the closed
token set MS-12-006 names, the domain-English shapes it must leave alone, and
the carrier counts the MS-12-007 and MS-12-008 ratchets read.
"""

import pytest

from vultron.metadata.specs.kind_classification import (
    code_reference_in,
    count_missing_story_suppressions,
    count_suppressions,
)
from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.schema import LintWarningCode, StatementSpec
from test.metadata.specs._helpers import write_yaml


def _spec(**fields) -> StatementSpec:
    base = {
        "id": "TST-01-001",
        "priority": "MUST",
        "kind": "protocol",
        "statement": "TST-01-001 MUST do the thing",
    }
    base.update(fields)
    return StatementSpec.model_validate(base)


@pytest.mark.parametrize(
    ("text", "token"),
    [
        ("Pinned by `test/metadata/conftest.py`", "test/metadata/conftest.py"),
        ("The whole `.py` suffix counts", ".py"),
        ("Everything under `vultron/` is core", "vultron/"),
        ("Integration tests in `test/demo/` confirm it", "test/demo/"),
        ("Run `scripts/backfill.sh` first", "scripts/backfill.sh"),
        ("A pytest fixture seeds the store", "pytest"),
        ("Validated by a pydantic model_validator", "pydantic"),
        ("Enforced via the Pydantic model", "Pydantic"),
        ("Run under PyTest in CI", "PyTest"),
        ("Composed from py_trees Selectors", "py_trees"),
    ],
)
def test_each_ms12_token_is_detected_and_named_whole(text, token):
    """Every member of MS-12-006's closed set matches, widened to its path."""
    assert code_reference_in(_spec(statement=text)) == ("statement", token)


@pytest.mark.parametrize(
    "text",
    [
        "The entry carries `case_id` and `log_index`",
        "A machine-readable failure class MUST accompany the Reject",
        "The actor's function in the CVD process",
        "The `module` field names the emitting component",
        "The `latest/` collection page lists recent cases",
        "Type stubs live in `.pyi` files",
        "Ignore the `.pytest_cache` directory",
        "A contest/ between two proposals is resolved by the owner",
        "Reader pages under `docs/test/` are excluded",
    ],
)
def test_domain_english_and_lookalikes_do_not_match(text):
    """Backticked wire field names, bare `module`/`class`/`function`, and
    tokens that merely contain a code word are not codebase references."""
    assert code_reference_in(_spec(statement=text)) is None


def test_token_is_not_widened_across_a_line_break():
    """The reported token stops at a newline before the match, not just at the start of the text."""
    hit = code_reference_in(
        _spec(statement="Pinned by the ratchet.\ntest/architecture/test_x.py")
    )
    assert hit == ("statement", "test/architecture/test_x.py")


def test_verification_is_scanned_after_statement():
    """A clean statement does not shield a verification that names code."""
    spec = _spec(verification="Covered by `test/demo/test_flow.py`")
    assert code_reference_in(spec) == (
        "verification",
        "test/demo/test_flow.py",
    )


def test_statement_hit_wins_over_verification_hit():
    spec = _spec(
        statement="Nodes MUST be py_trees behaviours",
        verification="Covered by `test/demo/test_flow.py`",
    )
    assert code_reference_in(spec) == ("statement", "py_trees")


def _registry_with_carriers(tmp_path):
    def item(spec_id, kind, priority, **extra):
        return {
            "id": spec_id,
            "priority": priority,
            "kind": kind,
            "statement": f"{spec_id} MUST do the thing",
            "rationale": "Because testing",
            **extra,
        }

    data = {
        "id": "TST",
        "title": "Test File",
        "description": "Test spec file",
        "scope": ["production"],
        "groups": [
            {
                "id": "TST-01",
                "title": "Group",
                "specs": [
                    # SR-11-003 would fire on this one
                    item(
                        "TST-01-001",
                        "protocol",
                        "MUST",
                        lint_suppress=["missing_story_reference"],
                    ),
                    # …but not on these two; MS-12-007 counts them regardless
                    item(
                        "TST-01-002",
                        "project",
                        "MUST",
                        lint_suppress=["missing_story_reference"],
                    ),
                    item(
                        "TST-01-003",
                        "protocol",
                        "SHOULD",
                        lint_suppress=[
                            "phantom_path_ref",
                            "missing_story_reference",
                        ],
                    ),
                    # a different code is not a carrier
                    item(
                        "TST-01-004",
                        "protocol",
                        "MUST",
                        stories=["story_2022_001"],
                        lint_suppress=["phantom_path_ref"],
                    ),
                    # MS-12-006's own escape hatch, ratcheted by MS-12-008
                    item(
                        "TST-01-005",
                        "protocol",
                        "MUST",
                        lint_suppress=[
                            "protocol_kind_with_code_reference",
                            "missing_story_reference",
                        ],
                    ),
                ],
            }
        ],
    }
    write_yaml(tmp_path, data)
    return load_registry(tmp_path)


def test_count_missing_story_suppressions_counts_every_carrier(tmp_path):
    """MS-12-007 counts carriers whether or not SR-11-003 would fire on them."""
    assert (
        count_missing_story_suppressions(_registry_with_carriers(tmp_path))
        == 4
    )


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (LintWarningCode.MISSING_STORY_REFERENCE, 4),
        (LintWarningCode.PROTOCOL_KIND_WITH_CODE_REFERENCE, 1),
        (LintWarningCode.PHANTOM_PATH_REF, 2),
    ],
)
def test_count_suppressions_counts_only_the_named_code(
    tmp_path, code, expected
):
    """MS-12-007 and MS-12-008 each count their own code's carriers."""
    assert (
        count_suppressions(_registry_with_carriers(tmp_path), code) == expected
    )
