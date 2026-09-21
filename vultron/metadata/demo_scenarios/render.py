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
"""Renderers for the artifacts derived from the demo scenario registry.

One data model — :class:`~vultron.demo.scenario.registry.ScenarioSpec` — feeds
several rendered tables through :func:`render_page`, following
:mod:`vultron.metadata.msm.render`.  Each slug is one *consumer shape*, because
the three consumers ask for different columns of the same rows:

============== =============================================== ==============
Slug           Consumer                                        Delivery
============== =============================================== ==============
``narratives`` ``docs/topics/scenarios/index.md``               build-time
``harnesses``  ``test/ci/README-case-log-ratchet.md``           marker block
``subcommands`` ``vultron/demo/scenario/README.md``             marker block
============== =============================================== ==============

``.github/demo-scenarios.json`` is rendered by
:func:`scenario_matrix_json` rather than as a page, because it is JSON and its
projection is deliberately narrower than any table (DEMOCI-11-004).

Usage from a ``markdown-exec`` Python block::

    from vultron.metadata.demo_scenarios.render import render_page
    print(render_page("narratives"))

Requirements: ``specs/demo-ci.yaml`` DEMOCI-11.  Design: ADR-0098.
"""

from __future__ import annotations

import json
from typing import Callable, Iterable, Mapping

from vultron.demo.scenario.registry import (
    MODULE_SUFFIX,
    ScenarioSpec,
    discover_scenarios,
)

#: The keys ``.github/demo-scenarios.json`` carries, in emitted order.
#:
#: Entries are splatted into ``matrix: include:``, so every key here becomes a
#: matrix variable visible to every step of two jobs.  Keep the projection
#: narrow: nothing belongs here that the workflow does not read
#: (DEMOCI-11-004).
MATRIX_KEYS: tuple[str, ...] = ("demo", "test_file", "full_suite_only")

#: Marks membership of the PR validation set in a rendered table.
_IN_SET = "✓"


def _cell(value: str) -> str:
    """Escape a value for use in a markdown table cell.

    A literal pipe would end the cell and shift every column after it, so it is
    replaced with its entity rather than left to corrupt the row.
    """
    return value.replace("|", "&#124;")


def _table(header: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    """Render a markdown table from *header* and *rows*.

    The alignment row is emitted as bare ``---`` for every column: cell content
    comes from prose the registry holds, and per-column alignment would be one
    more thing a renderer could disagree with a consumer about.
    """
    columns = [_cell(column) for column in header]
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join(["---"] * len(columns)) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_cell(cell) for cell in row) + " |")
    return "\n".join(lines)


def narrative_link(spec: ScenarioSpec) -> str:
    """Return the index page's link target for *spec*'s narrative page.

    A **built-site URL** (``fv/``), not a source path (``fv.md``), and that is
    not a style choice. MkDocs rewrites ``.md`` links to page URLs with a
    treeprocessor registered on its own ``Markdown`` instance; ``markdown-exec``
    converts a block's output on a *child* instance, which does not carry that
    treeprocessor. A ``.md`` target therefore survives into the built HTML
    verbatim and 404s — and ``mkdocs build --strict`` stays silent, because it
    never saw the link as an internal one to validate.

    Assumes ``use_directory_urls`` (the MkDocs default, and unset in
    ``mkdocs.yml``): with it disabled these would need to be ``fv.html``. That
    assumption is pinned by a test rather than left to this docstring, because
    flipping the setting would break every link here without failing the build.
    """
    return f"{spec.name}/"


def _narratives_table(specs: tuple[ScenarioSpec, ...]) -> str:
    """The narrative index table for ``docs/topics/scenarios/index.md``.

    Every narrative page is a sibling of the index, so links are relative to
    the index's own directory rather than a path from ``docs/``.
    """
    return _table(
        ("Short name", "Participants", "Notable protocol feature"),
        (
            (
                f"[{spec.label}]({narrative_link(spec)})",
                spec.participants,
                spec.feature,
            )
            for spec in specs
        ),
    )


def _harnesses_table(specs: tuple[ScenarioSpec, ...]) -> str:
    """The scenario→harness table for ``test/ci/README-case-log-ratchet.md``."""
    return _table(
        ("Scenario", "Test file", "In PR set"),
        (
            (
                spec.label,
                f"`{spec.harness_path}`",
                _IN_SET if spec.in_pr_set else "",
            )
            for spec in specs
        ),
    )


def _subcommands_table(specs: tuple[ScenarioSpec, ...]) -> str:
    """The sub-command table for ``vultron/demo/scenario/README.md``.

    Carries ``participants`` as its own column rather than folding it into the
    description: the hand-written descriptions this replaces mixed the two, and
    that is how the FCVCV row came to name four actors where the scenario has
    five.
    """
    return _table(
        ("Sub-command", "Script", "Participants", "What it demonstrates"),
        (
            (
                f"`{spec.name}`",
                f"`{spec.module_stem}{MODULE_SUFFIX}.py`",
                spec.participants,
                spec.feature,
            )
            for spec in specs
        ),
    )


_PAGES: Mapping[str, Callable[[tuple[ScenarioSpec, ...]], str]] = {
    "narratives": _narratives_table,
    "harnesses": _harnesses_table,
    "subcommands": _subcommands_table,
}

#: Canonical tuple of valid page slugs.
PAGE_SLUGS: tuple[str, ...] = tuple(_PAGES)


def render_page(
    slug: str,
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> str:
    """Render the scenario table for *slug* as markdown.

    Args:
        slug: One of :data:`PAGE_SLUGS`.
        specs: Scenarios to render. Defaults to
            :func:`~vultron.demo.scenario.registry.discover_scenarios`, which
            imports the whole scenario package. Pass an explicit tuple to
            render a hypothetical registry (the staleness tests do).

    Returns:
        A markdown table with no trailing newline, ready to splice between
        markers or print from a ``markdown-exec`` block.

    Raises:
        ValueError: When *slug* is not a known page.
    """
    if slug not in _PAGES:
        valid = ", ".join(PAGE_SLUGS)
        raise ValueError(f"Unknown page slug {slug!r}. Valid slugs: {valid}")
    resolved = discover_scenarios() if specs is None else specs
    return _PAGES[slug](resolved)


def matrix_entries(
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> list[dict[str, object]]:
    """Return the CI matrix projection of *specs* as plain dicts.

    ``full_suite_only`` is always present and always a real boolean: the
    workflow's selection filter is ``select(.full_suite_only == false)``, so an
    omitted field makes a PR-set scenario vanish from the matrix silently
    instead of erroring (DEMOCI-11-004).
    """
    resolved = discover_scenarios() if specs is None else specs
    return [
        {
            "demo": spec.name,
            "test_file": spec.harness_path,
            "full_suite_only": spec.full_suite_only,
        }
        for spec in resolved
    ]


def scenario_matrix_json(
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> str:
    """Return the desired contents of ``.github/demo-scenarios.json``."""
    return json.dumps(matrix_entries(specs), indent=2) + "\n"


__all__ = [
    "MATRIX_KEYS",
    "PAGE_SLUGS",
    "matrix_entries",
    "narrative_link",
    "render_page",
    "scenario_matrix_json",
]
