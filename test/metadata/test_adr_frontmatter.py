"""Tests for vultron.metadata.adr schema and loader.

Validation test requirement: specs/meta-specifications.yaml MS-14 (ADR-0043).
"""

import pytest
from pydantic import ValidationError

from test.metadata._adr_stubs import write_adr_stub as _adr
from vultron.metadata.adr.loader import load_adr_registry
from vultron.metadata.adr.schema import SUPERSESSION_FIELDS, AdrFrontmatter
from vultron.metadata.docs.page_schema import StakeholderType
from vultron.metadata.specs.schema import AdrStatus

_LC = {"created": "2020-01-01", "updated": "2020-01-01", "revision": 1}


class TestAdrFrontmatterSchema:
    def test_minimal_valid(self):
        fm = AdrFrontmatter.model_validate({**_LC, "status": "accepted"})
        assert fm.status is AdrStatus.ACCEPTED

    def test_all_status_values_accepted(self):
        for status in (
            "proposed",
            "accepted",
            "accepted-provisional",
            "rejected",
        ):
            fm = AdrFrontmatter.model_validate({**_LC, "status": status})
            assert fm.status.value == status

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            AdrFrontmatter.model_validate({**_LC, "status": "kinda-accepted"})

    def test_deciders_accepts_string_or_list(self):
        assert (
            AdrFrontmatter.model_validate(
                {**_LC, "status": "accepted", "deciders": "adh"}
            ).deciders
            == "adh"
        )
        assert AdrFrontmatter.model_validate(
            {**_LC, "status": "accepted", "deciders": ["adh", "Copilot"]}
        ).deciders == ["adh", "Copilot"]

    def test_date_parsed(self):
        fm = AdrFrontmatter.model_validate(
            {**_LC, "status": "accepted", "date": "2026-07-29"}
        )
        assert fm.date is not None and fm.date.year == 2026

    def test_superseded_requires_superseded_by(self):
        with pytest.raises(ValidationError, match="superseded_by"):
            AdrFrontmatter.model_validate({**_LC, "status": "superseded"})

    def test_deprecated_requires_superseded_by(self):
        with pytest.raises(ValidationError, match="superseded_by"):
            AdrFrontmatter.model_validate({**_LC, "status": "deprecated"})

    def test_superseded_with_target_valid(self):
        fm = AdrFrontmatter.model_validate(
            {**_LC, "status": "superseded", "superseded_by": "0041-next.md"}
        )
        assert fm.status is AdrStatus.SUPERSEDED
        assert fm.superseded_by == ["0041-next.md"]

    def test_inline_superseded_form_normalised(self):
        """'superseded by <link>' collapses to superseded + superseded_by."""
        fm = AdrFrontmatter.model_validate(
            {**_LC, "status": "superseded by 0041-next.md"}
        )
        assert fm.status is AdrStatus.SUPERSEDED
        assert fm.superseded_by == ["0041-next.md"]

    def test_partially_superseded_by_is_a_declared_field(self):
        """Declared, not an extra key — pydantic drops unknown keys silently.

        ADR-0012 carried ``partially_superseded_by`` for a while as an undeclared
        key, so nothing read it: the index rendered ADR-0012 as wholly current
        and the loader never checked the target resolved.
        """
        fm = AdrFrontmatter.model_validate(
            {
                **_LC,
                "status": "accepted",
                "partially_superseded_by": "0072-per-actor-storage.md",
            }
        )
        assert fm.partially_superseded_by == ["0072-per-actor-storage.md"]

    def test_partially_superseded_does_not_retire_the_adr(self):
        """The whole point of the distinction: the ADR stays live.

        ``superseded`` moves an ADR to ``docs/adr/archived/`` and out of the
        default context sweep. ADR-0012 still holds decisions in force, so
        archiving it would hide them.
        """
        fm = AdrFrontmatter.model_validate(
            {
                **_LC,
                "status": "accepted",
                "partially_superseded_by": "0072-per-actor-storage.md",
            }
        )
        assert fm.status is AdrStatus.ACCEPTED
        assert fm.superseded_by == []

    def test_lint_suppress_valid_code(self):
        fm = AdrFrontmatter.model_validate(
            {
                **_LC,
                "status": "accepted",
                "lint_suppress": ["status_prose_contradiction"],
            }
        )
        assert fm.lint_suppress is not None

    def test_lint_suppress_unknown_code_rejected(self):
        with pytest.raises(ValidationError):
            AdrFrontmatter.model_validate(
                {**_LC, "status": "accepted", "lint_suppress": ["bogus_code"]}
            )

    def test_lint_suppress_empty_list_rejected(self):
        with pytest.raises(ValidationError, match="non-empty"):
            AdrFrontmatter.model_validate(
                {**_LC, "status": "accepted", "lint_suppress": []}
            )


@pytest.mark.spec("MS-14-011")
class TestSupersessionFieldsAreLists:
    """All four supersession fields hold lists; a scalar is a one-item list."""

    @pytest.mark.parametrize("field", SUPERSESSION_FIELDS)
    def test_defaults_to_empty(self, field):
        fm = AdrFrontmatter.model_validate({**_LC, "status": "accepted"})
        assert getattr(fm, field) == []

    @pytest.mark.parametrize("field", SUPERSESSION_FIELDS)
    def test_scalar_is_coerced_to_one_item_list(self, field):
        fm = AdrFrontmatter.model_validate(
            {**_LC, "status": "accepted", field: "0041-next.md"}
        )
        assert getattr(fm, field) == ["0041-next.md"]

    @pytest.mark.parametrize("field", SUPERSESSION_FIELDS)
    def test_list_is_kept(self, field):
        fm = AdrFrontmatter.model_validate(
            {**_LC, "status": "accepted", field: ["0041-a.md", "ADR-0042"]}
        )
        assert getattr(fm, field) == ["0041-a.md", "ADR-0042"]

    @pytest.mark.parametrize("field", SUPERSESSION_FIELDS)
    def test_empty_entry_is_rejected(self, field):
        with pytest.raises(ValidationError, match=field):
            AdrFrontmatter.model_validate(
                {**_LC, "status": "accepted", field: ["0041-a.md", ""]}
            )

    def test_retired_with_empty_list_still_requires_superseded_by(self):
        with pytest.raises(ValidationError, match="superseded_by"):
            AdrFrontmatter.model_validate(
                {**_LC, "status": "superseded", "superseded_by": []}
            )


@pytest.mark.spec("DF-11-012")
class TestAdrStakeholderType:
    """An ADR is working record, so it declares ``[project-contributor]``.

    The field must be declared on the model: an undeclared key is dropped
    silently, so a wrong value would validate (#3528 AC-6a).
    """

    def test_project_contributor_is_kept(self):
        fm = AdrFrontmatter.model_validate(
            {
                **_LC,
                "status": "accepted",
                "stakeholder_type": ["project-contributor"],
            }
        )
        assert fm.stakeholder_type == [StakeholderType.PROJECT_CONTRIBUTOR]

    @pytest.mark.parametrize(
        "value",
        [
            ["cvd-practitioner"],
            ["project-contributor", "platform-developer"],
            "ALL",
            "project-contributor",
            [],
        ],
        ids=["other-type", "extra-type", "all", "bare-scalar", "empty"],
    )
    def test_any_other_value_is_rejected(self, value):
        with pytest.raises(ValidationError, match="stakeholder_type"):
            AdrFrontmatter.model_validate(
                {**_LC, "status": "accepted", "stakeholder_type": value}
            )

    def test_every_committed_adr_declares_it(self):
        registry = load_adr_registry()
        undeclared = sorted(
            name
            for name, fm in registry.items()
            if fm.stakeholder_type is None
        )
        assert undeclared == []


@pytest.mark.spec("MS-14-011")
def test_all_adr_files_have_valid_frontmatter():
    """Every docs/adr/*.md (excluding index/README/template) validates.

    Also asserts every supersession pointer resolves to a real ADR and that
    every supersession link is recorded on both ADRs it joins (MS-14-011).
    """
    registry = load_adr_registry()
    assert len(registry) > 0, "ADR registry must not be empty"
    # If load_adr_registry() raises, the test fails with that diagnostic.


def test_loader_rejects_dangling_superseded_by(tmp_path):
    """A superseded_by that resolves to no file is a load error."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-x.md").write_text(
        "---\nstatus: superseded\ncreated: 2020-01-01\nupdated: 2020-01-01\nrevision: 1\nsuperseded_by: 9999-nope.md\n---\n# x\n"
    )
    with pytest.raises(ValueError, match="superseded_by"):
        load_adr_registry(tmp_path)


def test_loader_rejects_dangling_partially_superseded_by(tmp_path):
    """The same check as ``superseded_by``, for the same reason.

    This branch had its own ADR renumbered three times (0066 → 0069 → 0070 →
    0072) because ``main`` landed a different ADR at each number first. A pointer
    written before a renumber rots, and an unvalidated one rots silently.
    """
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-x.md").write_text(
        "---\nstatus: accepted\ncreated: 2020-01-01\nupdated: 2020-01-01\nrevision: 1\n"
        "partially_superseded_by: 9999-nope.md\n---\n# x\n"
    )
    with pytest.raises(ValueError, match="partially_superseded_by"):
        load_adr_registry(tmp_path)


def test_loader_raises_valueerror_on_malformed_yaml(tmp_path):
    """A malformed YAML frontmatter block surfaces as ValueError, not a raw
    parser traceback — so spec-lint and the pre-commit hooks report a clean,
    file-attributed error (MS-14-001) instead of crashing.
    """
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    # Unclosed flow sequence → yaml.parser.ParserError inside frontmatter.load.
    (adr_dir / "0001-broken.md").write_text(
        "---\nstatus: accepted\ncreated: 2020-01-01\nupdated: 2020-01-01\nrevision: 1\ndeciders: [unclosed\n---\n# broken\n"
    )
    with pytest.raises(ValueError, match="malformed YAML frontmatter"):
        load_adr_registry(tmp_path)


# ---------------------------------------------------------------------------
# Two-way supersession links (MS-14-011)
# ---------------------------------------------------------------------------


@pytest.fixture
def adr_dir(tmp_path):
    return tmp_path / "docs" / "adr"


# The successor (0002) is named in each pointer form the loader accepts.
_POINTER_FORMS = {
    "bare-filename": "0002-new.md",
    "docs-path": "docs/adr/0002-new.md",
    "adr-number": "ADR-0002",
}
# The retired ADR (0001, archived) likewise.
_RETIRED_POINTER_FORMS = {
    "bare-filename": "0001-old.md",
    "docs-path": "docs/adr/archived/0001-old.md",
    "adr-number": "ADR-0001",
}


@pytest.mark.spec("MS-14-011")
class TestTwoWaySupersession:
    @pytest.mark.parametrize("fwd_form", _POINTER_FORMS)
    @pytest.mark.parametrize("back_form", _RETIRED_POINTER_FORMS)
    def test_full_supersession_pair_loads_in_any_pointer_form(
        self, tmp_path, adr_dir, fwd_form, back_form
    ):
        """Pointers are compared by ADR number, whatever form each is in."""
        _adr(
            adr_dir / "archived",
            "0001-old.md",
            status="superseded",
            superseded_by=_POINTER_FORMS[fwd_form],
        )
        _adr(
            adr_dir,
            "0002-new.md",
            supersedes=_RETIRED_POINTER_FORMS[back_form],
        )
        registry = load_adr_registry(tmp_path)
        assert len(registry) == 2

    @pytest.mark.parametrize("fwd_form", _POINTER_FORMS)
    @pytest.mark.parametrize("back_form", _RETIRED_POINTER_FORMS)
    def test_partial_supersession_pair_loads_in_any_pointer_form(
        self, tmp_path, adr_dir, fwd_form, back_form
    ):
        old = _RETIRED_POINTER_FORMS[back_form].replace("archived/", "")
        _adr(
            adr_dir,
            "0001-old.md",
            partially_superseded_by=_POINTER_FORMS[fwd_form],
        )
        _adr(adr_dir, "0002-new.md", partially_supersedes=old)
        assert len(load_adr_registry(tmp_path)) == 2

    @pytest.mark.parametrize("form", _POINTER_FORMS)
    def test_superseded_by_without_supersedes_fails(
        self, tmp_path, adr_dir, form
    ):
        _adr(
            adr_dir / "archived",
            "0001-old.md",
            status="superseded",
            superseded_by=_POINTER_FORMS[form],
        )
        _adr(adr_dir, "0002-new.md")
        with pytest.raises(ValueError) as exc:
            load_adr_registry(tmp_path)
        message = str(exc.value)
        assert "docs/adr/archived/0001-old.md: superseded_by" in message
        assert "docs/adr/0002-new.md has no supersedes entry" in message

    @pytest.mark.parametrize("form", _RETIRED_POINTER_FORMS)
    def test_supersedes_without_superseded_by_fails(
        self, tmp_path, adr_dir, form
    ):
        """The successor side alone is one-sided too."""
        _adr(
            adr_dir / "archived",
            "0001-old.md",
            status="deprecated",
            superseded_by="0003-other.md",
        )
        _adr(adr_dir, "0003-other.md", supersedes="0001-old.md")
        _adr(adr_dir, "0002-new.md", supersedes=_RETIRED_POINTER_FORMS[form])
        with pytest.raises(ValueError) as exc:
            load_adr_registry(tmp_path)
        message = str(exc.value)
        assert "docs/adr/0002-new.md: supersedes" in message
        assert (
            "docs/adr/archived/0001-old.md has no superseded_by entry"
            in message
        )

    @pytest.mark.parametrize("form", _POINTER_FORMS)
    def test_partially_superseded_by_without_partially_supersedes_fails(
        self, tmp_path, adr_dir, form
    ):
        _adr(
            adr_dir,
            "0001-old.md",
            partially_superseded_by=_POINTER_FORMS[form],
        )
        _adr(adr_dir, "0002-new.md")
        with pytest.raises(ValueError) as exc:
            load_adr_registry(tmp_path)
        message = str(exc.value)
        assert "docs/adr/0001-old.md: partially_superseded_by" in message
        assert "docs/adr/0002-new.md has no partially_supersedes entry" in (
            message
        )

    @pytest.mark.parametrize(
        "form", ["0001-old.md", "docs/adr/0001-old.md", "ADR-0001"]
    )
    def test_partially_supersedes_without_partially_superseded_by_fails(
        self, tmp_path, adr_dir, form
    ):
        _adr(adr_dir, "0001-old.md")
        _adr(adr_dir, "0002-new.md", partially_supersedes=form)
        with pytest.raises(ValueError) as exc:
            load_adr_registry(tmp_path)
        message = str(exc.value)
        assert "docs/adr/0002-new.md: partially_supersedes" in message
        assert (
            "docs/adr/0001-old.md has no partially_superseded_by entry"
            in message
        )

    def test_full_link_does_not_satisfy_a_partial_one(self, tmp_path, adr_dir):
        """The pairs are distinct: ``supersedes`` does not answer ``partially``."""
        _adr(adr_dir, "0001-old.md", partially_superseded_by="0002-new.md")
        _adr(adr_dir, "0002-new.md", supersedes="0001-old.md")
        with pytest.raises(ValueError, match="partially_supersedes"):
            load_adr_registry(tmp_path)

    def test_list_valued_links_load(self, tmp_path, adr_dir):
        """ADR-0099's shape: one successor retiring two ADRs."""
        for name in ("0001-a.md", "0002-b.md"):
            _adr(
                adr_dir / "archived",
                name,
                status="superseded",
                superseded_by="0003-new.md",
            )
        _adr(adr_dir, "0003-new.md", supersedes=["0001-a.md", "ADR-0002"])
        assert len(load_adr_registry(tmp_path)) == 3

    def test_list_missing_one_entry_fails_naming_it(self, tmp_path, adr_dir):
        for name in ("0001-a.md", "0002-b.md"):
            _adr(
                adr_dir / "archived",
                name,
                status="superseded",
                superseded_by="0003-new.md",
            )
        _adr(adr_dir, "0003-new.md", supersedes=["0001-a.md"])
        with pytest.raises(ValueError) as exc:
            load_adr_registry(tmp_path)
        message = str(exc.value)
        assert "archived/0002-b.md: superseded_by" in message
        assert "0001-a.md: superseded_by" not in message

    def test_every_fault_is_reported(self, tmp_path, adr_dir):
        """All one-sided links in the corpus surface in one error (EH-07-001)."""
        _adr(adr_dir, "0001-a.md", partially_superseded_by="0003-new.md")
        _adr(adr_dir, "0002-b.md", partially_superseded_by="0003-new.md")
        _adr(adr_dir, "0003-new.md")
        with pytest.raises(ValueError) as exc:
            load_adr_registry(tmp_path)
        message = str(exc.value)
        assert "0001-a.md: partially_superseded_by" in message
        assert "0002-b.md: partially_superseded_by" in message

    @pytest.mark.parametrize("field", ["supersedes", "partially_supersedes"])
    def test_dangling_successor_side_entry_fails(
        self, tmp_path, adr_dir, field
    ):
        """The successor-side fields must resolve, like ``superseded_by``."""
        _adr(adr_dir, "0001-new.md", **{field: "9999-nope.md"})
        with pytest.raises(ValueError, match=f"{field} '9999-nope.md'"):
            load_adr_registry(tmp_path)

    def test_dangling_adr_number_entry_fails(self, tmp_path, adr_dir):
        _adr(adr_dir, "0001-new.md", supersedes=["ADR-9999"])
        with pytest.raises(ValueError, match="supersedes 'ADR-9999'"):
            load_adr_registry(tmp_path)

    def test_pointer_to_a_non_adr_file_fails(self, tmp_path, adr_dir):
        """A numbered file that is not markdown is not an ADR to link to."""
        _adr(adr_dir, "0001-new.md", supersedes="0002-notes.txt")
        (adr_dir / "0002-notes.txt").write_text("not an ADR\n")
        with pytest.raises(ValueError, match=r"supersedes '0002-notes\.txt'"):
            load_adr_registry(tmp_path)

    def test_self_link_fails(self, tmp_path, adr_dir):
        """A link joins two ADRs; one naming itself is not two-way."""
        _adr(
            adr_dir,
            "0001-a.md",
            partially_superseded_by="0001-a.md",
            partially_supersedes="0001-a.md",
        )
        with pytest.raises(ValueError, match="names the ADR itself"):
            load_adr_registry(tmp_path)

    def test_link_to_a_shared_number_fails(self, tmp_path, adr_dir):
        """A number two files claim is no single target to check against."""
        _adr(adr_dir, "0001-a.md", partially_superseded_by="0002-new.md")
        _adr(adr_dir, "0002-new.md", partially_supersedes="0001-a.md")
        _adr(adr_dir / "archived", "0001-z.md")
        with pytest.raises(ValueError) as exc:
            load_adr_registry(tmp_path)
        message = str(exc.value)
        assert "0002-new.md: partially_supersedes names ADR-0001" in message
        assert "2 files claim" in message
        assert "archived/0001-z.md" in message
