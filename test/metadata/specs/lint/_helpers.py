"""Shared fixtures-as-functions for the spec linter tests."""

from vultron.metadata.specs.schema import RFC2119Priority

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


#: MS-10-003: a MUST-tier fixture carries this so the per-item verification
#: check stays out of tests about other rules.
_VERIFIED = "A unit test checks it."


def _minimal_spec(spec_id="TST-01-001", priority="MUST", extra=None):
    spec = {
        "id": spec_id,
        "priority": priority,
        "kind": "protocol",
        "statement": f"{spec_id} MUST do the thing",
        "rationale": "Because testing",
        "tags": ["testing"],
        "stories": ["story_2022_001"],
    }
    if RFC2119Priority(priority).is_must_tier:
        # MS-10-003: keep the per-item verification check out of the way.
        spec["verification"] = _VERIFIED
    if extra:
        spec.update(extra)
    return {
        "id": "TST",
        "title": "Test File",
        "description": "Test spec file",
        "scope": ["production"],
        "groups": [
            {
                "id": "TST-01",
                "title": "Group",
                "specs": [spec],
            }
        ],
    }


# ---------------------------------------------------------------------------
# ADR reference check (dangling_adr_ref) — advisory, non-blocking
# ---------------------------------------------------------------------------


def _make_adr_dir(tmp_path, adr_numbers=None):
    """Create a fake docs/adr/ directory with stub ADR files."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    for num in adr_numbers or []:
        # Valid status frontmatter so the MS-14-001 status check (which runs
        # over every ADR in the dir) does not flag these reference stubs.
        (adr_dir / f"{num}-stub.md").write_text(
            f"---\nstatus: accepted\ncreated: 2020-01-01\nupdated: 2020-01-01\nrevision: 1\n---\n# ADR-{num}\n"
        )
    return adr_dir


# ---------------------------------------------------------------------------
# MS-15-001: phantom path references in spec statements
# ---------------------------------------------------------------------------


def _repo_with_specs(tmp_path):
    """Return (repo_root, spec_dir) — lint() treats spec_dir.parent as the root.

    Creates the top-level directories the phantom-path tests reference, so a
    match is exercised against the existence check rather than being skipped as
    a package-relative illustration.
    """
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    for name in ("vultron", "test", ".claude", "docs"):
        (tmp_path / name).mkdir()
    return tmp_path, spec_dir


# ---------------------------------------------------------------------------
# SR-11: missing_story_reference — hard error (MUST) and advisory (SHOULD/MAY)
# ---------------------------------------------------------------------------


def _minimal_spec_no_stories(priority="MUST", kind="protocol"):
    """Return a minimal spec file with NO stories: field."""
    spec = {
        "id": "TST-01-001",
        "priority": priority,
        "kind": kind,
        "statement": "TST-01-001 MUST do the thing",
        "rationale": "Because testing",
        "tags": ["testing"],
    }
    if RFC2119Priority(priority).is_must_tier:
        spec["verification"] = _VERIFIED
    return {
        "id": "TST",
        "title": "Test File",
        "description": "Test spec file",
        "scope": ["production"],
        "groups": [{"id": "TST-01", "title": "Group", "specs": [spec]}],
    }


def _write_dated_adr(adr_dir, num, status, updated, override=""):
    (adr_dir / f"{num}-stub.md").write_text(
        f"---\nstatus: {status}\ncreated: {updated}\nupdated: {updated}\n"
        f"revision: 1\n{override}---\n# ADR-{num}\n"
    )
