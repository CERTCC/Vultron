"""CI verification test — the docs workflow runs on every source a page renders from.

Implements DOCBW-02-001 from ``specs/docs-build-workflow.yaml`` (#3070).

A page is not only its ``docs/`` file. The API reference is mkdocstrings over
``vultron/``; the ActivityPub how-to blocks print
``vultron/wire/as2/vocab/examples/``; the spec reference pages render ``specs/*.yaml``; the scenario
table and What's New are generators under ``vultron/metadata/``. When the
``pull_request`` trigger listed ``docs/**`` but neither ``vultron/**`` nor
``specs/**``, a PR that broke every one of those pages never ran the workflow
— #2904 broke every example block that way, and #3574 shipped a dead link
the same way. Every gate the workflow carries is only as wide as this trigger.
"""

from __future__ import annotations

import pytest

from test.ci._workflows import WORKFLOWS_DIR, load_workflow, triggers

WORKFLOW = WORKFLOWS_DIR / "docs-build-check.yml"

# Each is a directory that pages render from at build time, outside docs/.
RENDER_SOURCES = ("vultron/**", "specs/**")


def _pull_request_paths() -> list[str]:
    event = triggers(load_workflow(WORKFLOW)).get("pull_request") or {}
    paths = event.get("paths", []) if isinstance(event, dict) else []
    assert paths, (
        f"{WORKFLOW.name} has no pull_request paths: filter, so this test "
        "checks nothing (DF-09-009)."
    )
    return [str(p) for p in paths]


@pytest.mark.spec("DOCBW-02-001")
@pytest.mark.parametrize("source", RENDER_SOURCES)
def test_docs_workflow_triggers_on_page_render_source(source: str):
    assert source in _pull_request_paths(), (
        f"{WORKFLOW.name} does not trigger on {source!r}, so a PR changing only "
        "the code or specs that render pages never builds the site "
        "(DOCBW-02-001, #3070)."
    )


# The rest of DOCBW-02-001's list: widening the trigger must not drop these.
PAGE_SOURCES = (
    "docs/**",
    "overrides/**",
    "mkdocs.yml",
    "pyproject.toml",
    "uv.lock",
    ".github/actions/check-site-publication/**",
    ".github/workflows/docs-build-check.yml",
)


@pytest.mark.spec("DOCBW-02-001")
@pytest.mark.parametrize("source", PAGE_SOURCES)
def test_docs_workflow_still_triggers_on_page_source(source: str):
    assert (
        source in _pull_request_paths()
    ), f"{WORKFLOW.name} no longer triggers on {source!r} (DOCBW-02-001)."


@pytest.mark.spec("DOCBW-02-003")
def test_docs_workflow_does_not_trigger_on_all_markdown():
    assert "**/*.md" not in _pull_request_paths()
