"""Tests for vultron.metadata.specs.lint.phantom_symbols: phantom spec-ID
citations (SR-04-008) and phantom symbols (MS-15-004, MS-15-005).
"""

import re

import pytest

import vultron.metadata.specs.lint.phantom_symbols as lint_module
from test.metadata.specs._helpers import write_yaml
from test.metadata.specs.lint._helpers import _minimal_spec, _repo_with_specs
from vultron.metadata.specs.lint import lint

# ---------------------------------------------------------------------------
# _check_phantom_spec_id_citations (SR-04-008)
# ---------------------------------------------------------------------------


def test_phantom_spec_id_unknown_in_vultron_is_hard_error(tmp_path, capsys):
    """A .py file under vultron/ citing an unknown spec ID is a hard error."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    write_yaml(spec_dir, _minimal_spec())
    vultron_dir = tmp_path / "vultron"
    vultron_dir.mkdir()
    (vultron_dir / "module.py").write_text('"""Spec: XX-99-001."""\n')

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "XX-99-001" in captured.err


def test_phantom_spec_id_known_id_no_error(tmp_path, capsys):
    """A .py file under vultron/ citing a known spec ID returns 0."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    write_yaml(spec_dir, _minimal_spec())
    vultron_dir = tmp_path / "vultron"
    vultron_dir.mkdir()
    (vultron_dir / "module.py").write_text(
        '"""Spec: TST-01-001 MUST do the thing."""\n'
    )

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "[ERROR]" not in captured.err


def test_phantom_spec_id_allowlisted_dir_no_error(tmp_path, capsys):
    """Files under test/metadata/specs/ citing synthetic IDs are not flagged."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    write_yaml(spec_dir, _minimal_spec())
    allowlist_dir = tmp_path / "test" / "metadata" / "specs"
    allowlist_dir.mkdir(parents=True)
    (allowlist_dir / "test_fixture.py").write_text(
        '"""Uses synthetic IDs like XX-99-001."""\n'
    )

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "[ERROR]" not in captured.err


def test_phantom_spec_id_no_ids_in_file_no_error(tmp_path):
    """A .py file with no spec ID tokens returns 0."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    write_yaml(spec_dir, _minimal_spec())
    vultron_dir = tmp_path / "vultron"
    vultron_dir.mkdir()
    (vultron_dir / "module.py").write_text("def hello():\n    return 42\n")

    assert lint(spec_dir) == 0


def test_phantom_spec_id_unknown_in_test_dir_is_hard_error(tmp_path, capsys):
    """A .py file under a non-allowlisted test/ subdir citing an unknown spec ID is a hard error."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    write_yaml(spec_dir, _minimal_spec())
    test_core_dir = tmp_path / "test" / "core"
    test_core_dir.mkdir(parents=True)
    (test_core_dir / "test_something.py").write_text(
        '"""Spec: XX-99-001."""\n'
    )

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "XX-99-001" in captured.err


# ---------------------------------------------------------------------------
# MS-15-004 / MS-15-005: phantom symbol references in spec statements
# ---------------------------------------------------------------------------


def test_lint_phantom_symbol_is_hard_error(tmp_path, capsys):
    """A statement naming a SCREAMING_SNAKE symbol absent from the tree fails."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Every pattern MUST be registered in `RETIRED_PATTERN_TABLE`"
    )
    write_yaml(spec_dir, data)

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-004" in captured.err
    assert "RETIRED_PATTERN_TABLE" in captured.err


def test_lint_phantom_symbol_existing_symbol_passes(tmp_path):
    """A statement naming a symbol defined under vultron/ is accepted."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "registry.py").write_text(
        "LIVE_PATTERN_TABLE: dict = {}\n"
    )
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Every pattern MUST be registered in `LIVE_PATTERN_TABLE`"
    )
    write_yaml(spec_dir, data)

    assert lint(spec_dir) == 0


def test_lint_phantom_symbol_resolves_from_test_tree(tmp_path):
    """A symbol that only exists under test/ still resolves (MS-15-004)."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "test" / "test_thing.py").write_text("KNOWN_VIOLATIONS = ()\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "The ratchet MUST enumerate exemptions in `KNOWN_VIOLATIONS`"
    )
    write_yaml(spec_dir, data)

    assert lint(spec_dir) == 0


def test_lint_phantom_symbol_in_verification_is_hard_error(tmp_path, capsys):
    """The verification field is scanned for phantom symbols too."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["verification"] = (
        "A unit test asserts `GONE_REGISTRY` has one entry per semantic."
    )
    write_yaml(spec_dir, data)

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "GONE_REGISTRY" in captured.err


def test_lint_phantom_symbol_rationale_not_scanned(tmp_path):
    """rationale may name a removed symbol as the problem it prevents."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["rationale"] = (
        "`GONE_REGISTRY` was replaced during the registry move."
    )
    write_yaml(spec_dir, data)

    assert lint(spec_dir) == 0


def test_lint_phantom_symbol_suppress(tmp_path, capsys):
    """lint_suppress: [phantom_symbol_ref] allows a deliberate mention (MS-15-005)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec(extra={"lint_suppress": ["phantom_symbol_ref"]})
    data["groups"][0]["specs"][0]["statement"] = (
        "The `REMOVED_SEMANTIC_TABLE` table has been removed; use the registry."
    )
    write_yaml(spec_dir, data)

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-15-004" not in captured.err


def test_lint_phantom_symbol_linter_own_source_excluded_from_corpus(
    tmp_path, capsys
):
    """A symbol appearing only under `vultron/metadata/specs/` is not live.

    The linter's own modules quote retired symbol names in docstrings and error
    messages. Counting those as corpus entries would make the check resolve the
    very tokens it exists to reject.
    """
    repo, spec_dir = _repo_with_specs(tmp_path)
    linter_dir = repo / "vultron" / "metadata" / "specs" / "lint"
    linter_dir.mkdir(parents=True)
    (linter_dir / "phantom_symbols.py").write_text(
        '"""Catches references to `RETIRED_TABLE`."""\n'
    )
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Patterns MUST be registered in `RETIRED_TABLE`"
    )
    write_yaml(spec_dir, data)

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "RETIRED_TABLE" in captured.err


def test_lint_phantom_symbol_linter_sibling_still_in_corpus(tmp_path):
    """A symbol defined only in a sibling of lint.py (e.g. schema.py) resolves.

    The corpus exclusion is scoped to ``lint.py`` itself, not the whole
    ``vultron/metadata/specs/`` package: ``schema.py`` defines symbols the specs
    legitimately cite (``RFC2119Priority`` members such as ``SHOULD_NOT``), so
    excluding the package would reject real references. This pins that scoping
    decision — the mirror of
    :func:`test_lint_phantom_symbol_linter_own_source_excluded_from_corpus`.
    """
    repo, spec_dir = _repo_with_specs(tmp_path)
    linter_dir = repo / "vultron" / "metadata" / "specs"
    linter_dir.mkdir(parents=True)
    (linter_dir / "schema.py").write_text("SHOULD_NOT = 'should_not'\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "The priority MUST NOT be `SHOULD_NOT`"
    )
    write_yaml(spec_dir, data)

    assert lint(spec_dir) == 0


def test_lint_phantom_symbol_test_fixture_dir_excluded_from_corpus(
    tmp_path, capsys
):
    """Symbol names invented by the linter's own tests are not live either."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    fixture_dir = repo / "test" / "metadata" / "specs"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "test_lint.py").write_text(
        'STATEMENT = "MUST be in `INVENTED_TABLE`"\n'
    )
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Patterns MUST be registered in `INVENTED_TABLE`"
    )
    write_yaml(spec_dir, data)

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "INVENTED_TABLE" in captured.err


def test_lint_phantom_symbol_single_word_token_not_checked(tmp_path):
    """Underscore-free tokens (`MUST`, `RS`, `SIGNATORY`) are not symbols."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Shorthand `RS` MUST leave the participant `SIGNATORY`"
    )
    write_yaml(spec_dir, data)

    assert lint(spec_dir) == 0


def test_lint_phantom_symbol_dotted_reference_not_checked(tmp_path):
    """A dotted member reference is not a bare SCREAMING_SNAKE token."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "The fallback MUST be `MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT`"
    )
    write_yaml(spec_dir, data)

    assert lint(spec_dir) == 0


@pytest.mark.parametrize(
    "text",
    [
        "FOO_BAR",
        "x = FOO_BAR + _BAZ_QUX",
        "aFOO_BAR FOO_BAR2 9FOO_BAR",
        "éFOO_BAR ÉFOO_BAR",
        "FOO_BAR_ FOO__BAR F_1 A_B_C.D_E",
        "MUST RS FOO_V2 FOO_bar",
    ],
)
def test_source_symbol_re_matches_the_word_bounded_form(text):
    """The lookbehind spelling finds exactly what the ``\\b`` form does."""
    plain = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")

    assert lint_module.SOURCE_SYMBOL_RE.findall(text) == plain.findall(text)
