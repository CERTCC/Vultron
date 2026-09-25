"""Tests for vultron.metadata.docs.withheld (issue #3549).

``docs/ns/index.md`` carried ``draft: true`` and shipped anyway: ``draft`` is a
Material *blog-plugin* key, not an MkDocs one, so the frontmatter suppressed
nothing. The claim existed, the output contradicted it, and nothing compared
them. These tests pin the comparison.

Two of them are the load-bearing ones, because both close a way for the check to
pass while checking nothing: an absent ``site/`` must raise rather than report
clean, and a declaration whose source globs match no file must fail rather than
pass vacuously.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vultron.metadata.docs.withheld import (
    WITHHELD_ARTIFACTS,
    WithheldArtifact,
    main,
    published_violations,
    undeclared_artifacts,
)

REPO_ROOT = Path(__file__).parents[3]


def _artifact(**overrides) -> WithheldArtifact:
    """Build a throwaway declaration, overriding only what a test cares about."""
    defaults = {
        "name": "Test artifact",
        "site_prefixes": ("withheld",),
        "source_globs": ("docs/withheld/index.md",),
        "reason": "Test reason.",
        "gate": "Test gate.",
    }
    return WithheldArtifact(**{**defaults, **overrides})


def _build_tree(
    root: Path, site_paths: list[str], source_paths: list[str]
) -> None:
    """Create a synthetic checkout with a built site/ and a source tree."""
    for rel in [f"site/{p}" for p in site_paths] + source_paths:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")


# --- published_violations -------------------------------------------------


def test_no_violation_when_withheld_artifact_is_absent_from_site(tmp_path):
    _build_tree(
        tmp_path,
        site_paths=["index.html", "reference/index.html"],
        source_paths=["docs/withheld/index.md"],
    )
    assert published_violations(tmp_path, (_artifact(),)) == []


def test_violation_when_withheld_page_is_built(tmp_path):
    _build_tree(
        tmp_path,
        site_paths=["withheld/index.html"],
        source_paths=["docs/withheld/index.md"],
    )
    artifact = _artifact()
    violations = published_violations(tmp_path, (artifact,))
    assert [a.name for a, _ in violations] == [artifact.name, artifact.name]
    # The directory itself and the file inside it are both reported, so the
    # message names the page rather than only the enclosing directory.
    built = {str(p.relative_to(tmp_path)) for _, p in violations}
    assert built == {"site/withheld", "site/withheld/index.html"}


def test_violation_catches_a_static_file_not_only_a_page(tmp_path):
    """`draft_docs` withholds static files too, so the check must see them.

    `ns/context.jsonld` is the reason: it is the artifact that would actually
    make the namespace URI resolve, and it is not a Markdown page.
    """
    _build_tree(
        tmp_path,
        site_paths=["withheld/context.jsonld"],
        source_paths=["docs/withheld/index.md"],
    )
    violations = published_violations(tmp_path, (_artifact(),))
    built = {str(p.relative_to(tmp_path)) for _, p in violations}
    assert "site/withheld/context.jsonld" in built


def test_absent_site_raises_rather_than_reporting_clean(tmp_path):
    """An unbuilt site cannot evidence the claim, so it fails (DF-09-009)."""
    (tmp_path / "docs/withheld").mkdir(parents=True)
    (tmp_path / "docs/withheld/index.md").write_text("x", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="mkdocs build"):
        published_violations(tmp_path, (_artifact(),))


def test_empty_site_raises_rather_than_reporting_clean(tmp_path):
    (tmp_path / "site").mkdir()
    with pytest.raises(FileNotFoundError, match="mkdocs build"):
        published_violations(tmp_path, (_artifact(),))


def test_violations_are_sorted_for_stable_output(tmp_path):
    _build_tree(
        tmp_path,
        site_paths=["b/index.html", "a/index.html"],
        source_paths=["docs/a/index.md", "docs/b/index.md"],
    )
    artifacts = (
        _artifact(
            name="Zulu",
            site_prefixes=("b",),
            source_globs=("docs/b/index.md",),
        ),
        _artifact(
            name="Alpha",
            site_prefixes=("a",),
            source_globs=("docs/a/index.md",),
        ),
    )
    violations = published_violations(tmp_path, artifacts)
    names = [a.name for a, _ in violations]
    # Each artifact contributes several paths, so assert the artifacts appear in
    # name order and that one artifact's paths are not interleaved with another's.
    assert names == sorted(names)
    assert list(dict.fromkeys(names)) == ["Alpha", "Zulu"]
    paths = [str(p) for _, p in violations]
    assert paths == sorted(paths)


# --- undeclared_artifacts -------------------------------------------------


def test_declaration_matching_no_source_file_is_reported(tmp_path):
    """A declaration describing nothing would pass forever while checking nothing."""
    _build_tree(tmp_path, site_paths=["index.html"], source_paths=[])
    assert [
        a.name for a in undeclared_artifacts(tmp_path, (_artifact(),))
    ] == ["Test artifact"]


def test_declaration_matching_a_source_file_is_not_reported(tmp_path):
    _build_tree(
        tmp_path,
        site_paths=["index.html"],
        source_paths=["docs/withheld/index.md"],
    )
    assert undeclared_artifacts(tmp_path, (_artifact(),)) == []


def test_any_matching_source_glob_satisfies_the_declaration(tmp_path):
    """The globs are alternatives: the ontology entry matches a TTL glob."""
    _build_tree(
        tmp_path, site_paths=["index.html"], source_paths=["docs/other.md"]
    )
    artifact = _artifact(source_globs=("docs/missing.md", "docs/other.md"))
    assert undeclared_artifacts(tmp_path, (artifact,)) == []


# --- the live declaration -------------------------------------------------


def test_every_declared_artifact_exists_in_this_repo():
    """Guards the real declaration against a rename that would silently pass."""
    assert undeclared_artifacts(REPO_ROOT) == []


@pytest.mark.parametrize(
    "name",
    ["JSON-LD vocabulary", "OWL/TTL ontology", "Ledger replication spec"],
)
def test_the_three_withheld_artifacts_are_declared(name):
    """The publication axis #3555's manifest inherits; see that issue's table."""
    assert name in {a.name for a in WITHHELD_ARTIFACTS}


def test_ontology_tombstone_is_not_itself_withheld():
    """`reference/ontology/index.md` stays published; only the details went.

    #3551 keeps the tombstone answering the live URL, so a glob that swept the
    whole `reference/ontology/` directory would contradict that issue's AC-2.
    """
    ontology = next(
        a for a in WITHHELD_ARTIFACTS if a.name == "OWL/TTL ontology"
    )
    assert "reference/ontology" not in ontology.site_prefixes
    # Derived patterns must not sweep the directory either.
    assert "reference/ontology" not in ontology.site_globs()


def test_site_globs_pattern_is_portable_to_python_3_12():
    """A prefix derives `<prefix>/**/*`, never a bare `<prefix>/**`.

    Before Python 3.13 a pattern ending in `**` matched directories only, so
    `ns/**` skipped `site/ns/context.jsonld` — the exact file that makes the
    namespace URI resolve. The project supports 3.12+, so the pattern has to
    mean the same thing on both.
    """
    patterns = _artifact(site_prefixes=("ns",)).site_globs()
    assert patterns == ("ns", "ns/**/*")
    assert not any(p.endswith("/**") for p in patterns)


def test_every_real_artifact_derives_portable_patterns():
    for artifact in WITHHELD_ARTIFACTS:
        assert not any(p.endswith("/**") for p in artifact.site_globs())


# --- CLI ------------------------------------------------------------------


def test_main_exits_nonzero_when_a_withheld_artifact_is_published(
    tmp_path, capsys
):
    _build_tree(
        tmp_path,
        site_paths=["ns/context.jsonld"],
        source_paths=["docs/ns/index.md"],
    )
    with pytest.raises(SystemExit) as exc:
        main(["--root", str(tmp_path)])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "JSON-LD vocabulary" in err
    # The operator needs to know what unblocks publication, not only that it failed.
    assert "Gate on publishing:" in err
    # The JSON-LD file is the reason this artifact is withheld, so it must be
    # named. A bare `ns/**` pattern would report only the directory on 3.12.
    assert "site/ns/context.jsonld" in err


def test_main_reports_an_unbuilt_site_as_an_error_not_a_traceback(
    tmp_path, capsys
):
    """Error messages are this package's product; a traceback is not one."""
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["--root", str(tmp_path)])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert err.startswith("[ERROR]")
    assert "mkdocs build" in err


def test_main_succeeds_when_nothing_withheld_is_published(tmp_path, capsys):
    _build_tree(
        tmp_path,
        site_paths=["index.html"],
        source_paths=[
            "docs/ns/index.md",
            "docs/ns/context.jsonld",
            "ontology/vultron_protocol.ttl",
            "docs/reference/draft-vultron-replication-spec.md",
        ],
    )
    main(["--root", str(tmp_path)])
    assert "withheld artifacts are absent" in capsys.readouterr().out


# --- covers ---------------------------------------------------------------


@pytest.mark.parametrize(
    "site_path,covered",
    [
        ("withheld", True),
        ("withheld/index.html", True),
        ("withheld/deep/page", True),
        ("withheld2", False),
        ("other/withheld", False),
    ],
)
def test_covers_matches_a_prefix_and_what_is_beneath_it(site_path, covered):
    """The continuity check (#3556) leans on this to skip withdrawn URLs."""
    assert _artifact().covers(site_path) is covered
