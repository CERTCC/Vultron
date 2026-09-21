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
"""Ratchets over the artifacts generated from the demo scenario registry.

Three things are checked here, and they fail for different reasons on purpose:

* **The committed artifacts are current** (``test_committed_artifacts_are_in_sync``).
  This duplicates the ``demo-scenarios-sync`` pre-commit hook deliberately: a
  hook can be skipped with ``SKIP=`` or bypassed with ``--no-verify``, and a
  stale CI matrix is invisible until a demo job does not run.
* **The check mode actually fails on a stale artifact**
  (``test_check_detects_a_stale_*``).  A ``--check`` that passes unconditionally
  looks exactly like a repository in sync, so the gate needs its own negative
  evidence (DEMOCI-11-005).
* **The CI matrix projection stays narrow** (``test_matrix_carries_only_...``).
  Entries are splatted into ``matrix: include:``, so every extra key becomes a
  matrix variable in every step of two jobs (DEMOCI-11-004).

Requirements: ``specs/demo-ci.yaml`` DEMOCI-11-004, DEMOCI-11-005.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
import yaml

from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios
from vultron.metadata.base import MkDocsYamlLoader
from vultron.metadata.demo_scenarios.render import (
    MATRIX_KEYS,
    PAGE_SLUGS,
    matrix_entries,
    render_page,
    scenario_matrix_json,
)
from vultron.metadata.demo_scenarios.sync import (
    ARTIFACTS,
    BEGIN_MARKER,
    END_MARKER,
    HARNESS_README,
    MATRIX_JSON,
    SCENARIO_README,
    desired_contents,
    missing_derived_paths,
    splice,
    stale_artifacts,
    write_artifacts,
)

_REPO_ROOT = Path(__file__).parents[2]

#: The pre-commit hook that gates the committed artifacts (DEMOCI-11-005).
_SYNC_HOOK_ID = "demo-scenarios-sync"

#: Inputs the artifacts are derived from, standing in for "any change that makes
#: them stale": a scenario module (the registry) and a renderer (the projection).
_ARTIFACT_INPUTS = (
    "vultron/demo/scenario/fv_demo.py",
    "vultron/metadata/demo_scenarios/render.py",
)

#: A registry that differs from the committed one, used to make every artifact
#: stale at once without touching the real scenario modules.
_EXTRA_SPEC = ScenarioSpec(
    name="zz-fake",
    label="ZZ-fake",
    participants="Finder + Vendor",
    feature="Fixture scenario; never registered",
    in_pr_set=True,
)


@pytest.fixture
def artifact_root(tmp_path: Path) -> Path:
    """A throwaway tree holding copies of the three committed artifacts.

    Copied rather than generated so the staleness tests start from exactly what
    is committed; a fixture that wrote its own starting state could pass while
    the real files were already wrong.
    """
    for artifact in ARTIFACTS:
        source = _REPO_ROOT / artifact.path
        target = tmp_path / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return tmp_path


def test_committed_artifacts_are_in_sync() -> None:
    """Every committed artifact matches what the registry renders today."""
    stale = stale_artifacts(_REPO_ROOT)
    assert not stale, (
        f"generated scenario artifacts are stale: {stale}. Run "
        "'uv run demo-scenarios --write' and commit the result "
        "(DEMOCI-11-005)."
    )


def test_registered_scenarios_have_no_missing_derived_paths() -> None:
    """``--check`` reports no registered scenario with an unresolvable path."""
    assert missing_derived_paths(_REPO_ROOT) == []


def test_check_detects_a_stale_matrix_json(artifact_root: Path) -> None:
    """A hand-edited CI matrix is reported stale.

    Drops the first entry rather than editing a value, because a scenario
    vanishing from the matrix is the failure with no other symptom: the demo
    job for it simply never runs, and the workflow is green.
    """
    target = artifact_root / MATRIX_JSON
    entries = json.loads(target.read_text(encoding="utf-8"))
    target.write_text(
        json.dumps(entries[1:], indent=2) + "\n", encoding="utf-8"
    )

    assert stale_artifacts(artifact_root) == [MATRIX_JSON]


@pytest.mark.parametrize(
    ("path", "cell"),
    [
        (HARNESS_README, "`test/ci/invariants/test_fv_invariants.py`"),
        (SCENARIO_README, "Baseline two-actor CVD"),
    ],
    ids=["harnesses", "subcommands"],
)
def test_check_detects_a_hand_edited_table(
    artifact_root: Path, path: str, cell: str
) -> None:
    """A cell edited inside the markers is reported stale.

    The edited cell is one the *generated* table owns, asserted to be inside the
    marker block first: a substitution that happened to land in the surrounding
    prose would make this test pass while proving nothing about the table.
    """
    target = artifact_root / path
    text = target.read_text(encoding="utf-8")
    block = text.split(BEGIN_MARKER)[1].split(END_MARKER)[0]
    assert cell in block, f"{cell!r} is not in {path}'s generated block"

    target.write_text(text.replace(cell, "hand-edited"), encoding="utf-8")

    assert stale_artifacts(artifact_root) == [path]


def test_check_detects_every_artifact_when_the_registry_changes(
    artifact_root: Path,
) -> None:
    """Adding a scenario makes all three artifacts stale at once.

    The registry is passed explicitly: the point is that a *registry* change,
    not a file edit, is what the gate exists to propagate.
    """
    specs = discover_scenarios() + (_EXTRA_SPEC,)
    assert stale_artifacts(artifact_root, specs) == [
        artifact.path for artifact in ARTIFACTS
    ]


def test_write_then_check_round_trips(artifact_root: Path) -> None:
    """``--write`` makes ``--check`` clean, and is idempotent afterwards."""
    specs = discover_scenarios() + (_EXTRA_SPEC,)
    written = write_artifacts(artifact_root, specs)
    assert written == [artifact.path for artifact in ARTIFACTS]
    assert stale_artifacts(artifact_root, specs) == []
    assert write_artifacts(artifact_root, specs) == []


def test_write_preserves_hand_written_prose(artifact_root: Path) -> None:
    """Prose outside the markers survives a rewrite.

    The two markdown artifacts are mostly hand-written; only the table between
    the markers is generated. A splicer that rewrote the whole file would be
    silently destructive, and the loss would show up as missing documentation
    rather than as a failure.
    """
    target = artifact_root / HARNESS_README
    before = target.read_text(encoding="utf-8")
    sentinel = "## Adding a New Invariant"
    assert sentinel in before

    write_artifacts(artifact_root, discover_scenarios() + (_EXTRA_SPEC,))
    after = target.read_text(encoding="utf-8")

    assert sentinel in after
    assert after.split(BEGIN_MARKER)[0] == before.split(BEGIN_MARKER)[0]
    assert after.split(END_MARKER)[1] == before.split(END_MARKER)[1]
    assert "zz-fake" not in after.split(BEGIN_MARKER)[0]


def test_matrix_carries_only_the_keys_the_ci_matrix_consumes() -> None:
    """No key beyond ``demo``/``test_file``/``full_suite_only`` leaks in.

    Every key in an entry becomes a matrix variable visible to every step of
    both downstream jobs, so widening the projection is not a cosmetic change
    (DEMOCI-11-004).
    """
    entries = matrix_entries()
    assert entries, "the scenario registry produced an empty CI matrix"
    for entry in entries:
        assert tuple(entry) == MATRIX_KEYS, (
            f"matrix entry for {entry.get('demo')!r} carries keys "
            f"{tuple(entry)}; the CI matrix consumes only {MATRIX_KEYS}."
        )


def test_matrix_full_suite_only_is_an_explicit_boolean() -> None:
    """``full_suite_only`` is present and a real ``bool`` on every entry.

    The workflow filters with ``select(.full_suite_only == false)``, an exact
    comparison, so an omitted or truthy-non-boolean field drops a PR-set
    scenario from the matrix instead of erroring (DEMOCI-11-004).
    """
    for entry in json.loads(scenario_matrix_json()):
        assert isinstance(entry["full_suite_only"], bool), entry


def test_matrix_json_is_the_committed_projection_of_the_registry() -> None:
    """The committed JSON's demo/harness pairs are the registry's, exactly."""
    committed = json.loads(
        (_REPO_ROOT / MATRIX_JSON).read_text(encoding="utf-8")
    )
    expected = [
        {
            "demo": spec.name,
            "test_file": spec.harness_path,
            "full_suite_only": spec.full_suite_only,
        }
        for spec in discover_scenarios()
    ]
    assert committed == expected


def _sync_hook() -> dict[str, object]:
    """The ``demo-scenarios-sync`` hook definition from the pre-commit config."""
    config = yaml.safe_load(
        (_REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    hooks: list[dict[str, object]] = [
        hook
        for repo in config.get("repos", [])
        for hook in repo.get("hooks", [])
        if hook.get("id") == _SYNC_HOOK_ID
    ]
    assert len(hooks) == 1, (
        f"expected exactly one '{_SYNC_HOOK_ID}' pre-commit hook, found "
        f"{len(hooks)}. It is the commit-time gate for every generated "
        "scenario artifact (DEMOCI-11-005)."
    )
    return hooks[0]


def test_pre_commit_registers_the_check_mode() -> None:
    """The gate runs the dumper's ``--check`` mode, not something adjacent.

    Asserted on the entry string because a hook that ran ``--write`` would
    silently *fix* the tree and let a stale commit through green, which is the
    opposite of a gate.
    """
    entry = str(_sync_hook().get("entry", ""))
    assert "vultron.metadata.demo_scenarios.sync" in entry, entry
    assert "--check" in entry, entry
    assert "--write" not in entry, entry


@pytest.mark.parametrize(
    "path",
    [artifact.path for artifact in ARTIFACTS] + list(_ARTIFACT_INPUTS),
    ids=lambda path: path,
)
def test_pre_commit_hook_watches_every_input_and_artifact(path: str) -> None:
    """The hook fires on a change to any artifact *or* to any of its inputs.

    All three halves matter and they fail differently. Watching only the
    artifacts catches a hand-edit but not the cases that actually happen: a
    scenario added or re-flagged in a decorator, or a renderer that changes a
    column — either of which makes every artifact stale without touching one.
    """
    pattern = re.compile(str(_sync_hook().get("files", "")))
    assert pattern.search(path), (
        f"the '{_SYNC_HOOK_ID}' hook's files pattern does not match {path!r}, "
        "so a commit changing it would not run the check (DEMOCI-11-005)."
    )


def test_index_page_commits_no_scenario_table() -> None:
    """``docs/topics/scenarios/index.md`` renders its table, never stores one.

    A committed copy would render alongside the generated one and start
    drifting the moment a scenario changed (DEMOCI-11-009).
    """
    page = _REPO_ROOT / "docs" / "topics" / "scenarios" / "index.md"
    text = page.read_text(encoding="utf-8")
    assert "render_page(" in text, (
        "the narrative index no longer renders its scenario table at build "
        "time (DEMOCI-11-009)."
    )
    # Any table row naming a scenario, whatever link form it uses: a committed
    # copy is the defect, not a particular spelling of it.
    rows = [
        line
        for line in text.splitlines()
        if line.startswith("|")
        and any(spec.label in line for spec in discover_scenarios())
    ]
    assert not rows, (
        f"{page.name} commits scenario-table row(s):\n"
        + "\n".join(f"  {row}" for row in rows)
        + "\nThe table is rendered at build time and must not be checked in "
        "(DEMOCI-11-009)."
    )


@pytest.mark.parametrize("slug", PAGE_SLUGS)
def test_render_page_renders_every_scenario(slug: str) -> None:
    """Each consumer shape names every registered scenario exactly once."""
    specs = discover_scenarios()
    rendered = render_page(slug, specs)
    rows = [line for line in rendered.splitlines() if line.startswith("| ")]
    # header + separator are not rows; the separator does not start with "| ".
    assert len(rows) == len(specs) + 1, rendered
    for spec in specs:
        assert spec.label in rendered or spec.name in rendered


def test_render_page_rejects_an_unknown_slug() -> None:
    with pytest.raises(ValueError, match="Unknown page slug"):
        render_page("no-such-consumer")


def test_narrative_links_are_built_site_urls() -> None:
    """The index's links target page URLs, not ``.md`` source paths.

    ``markdown-exec`` converts a block's output on a child ``Markdown``
    instance, which does not carry the MkDocs treeprocessor that rewrites
    ``.md`` links to page URLs. A ``.md`` target therefore reaches the built
    HTML verbatim and 404s, and ``mkdocs build --strict`` does not complain
    because it never saw the link as an internal one.
    """
    rendered = render_page("narratives")
    assert ".md)" not in rendered, rendered
    for spec in discover_scenarios():
        assert f"[{spec.label}]({spec.name}/)" in rendered


def test_mkdocs_keeps_directory_urls() -> None:
    """``use_directory_urls`` is not disabled, which the link form assumes.

    With it off, pages build as ``fv.html`` and every link the narratives table
    renders would break — silently, since nothing validates those links. Pinned
    here because the assumption lives in a renderer, far from ``mkdocs.yml``.
    """
    config = yaml.load(
        (_REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8"),
        Loader=MkDocsYamlLoader,
    )
    assert config.get("use_directory_urls", True) is True, (
        "use_directory_urls is disabled, so built pages are '<name>.html' and "
        "the narratives table's '<name>/' links no longer resolve. Update "
        "vultron.metadata.demo_scenarios.render.narrative_link() to match."
    )


def test_splice_rejects_a_file_without_markers() -> None:
    """Missing markers fail rather than appending a second table.

    Appending would leave the stale copy in place above the new one — two
    tables on one subject, which is the drift this whole mechanism removes.
    """
    with pytest.raises(ValueError, match="found 0 generated-table begin"):
        splice("# A doc with no markers\n", "| a |\n", "some/doc.md")


def test_splice_rejects_inverted_markers() -> None:
    with pytest.raises(ValueError, match="end marker precedes"):
        splice(f"{END_MARKER}\n\n{BEGIN_MARKER}\n", "| a |", "some/doc.md")


def test_desired_contents_requires_the_marker_files_to_exist(
    tmp_path: Path,
) -> None:
    """A missing markdown artifact fails loudly instead of being invented.

    Its hand-written prose is not derivable from the registry, so there is
    nothing to splice into and writing a table-only file would delete
    documentation.
    """
    with pytest.raises(FileNotFoundError, match=HARNESS_README):
        desired_contents(tmp_path)
