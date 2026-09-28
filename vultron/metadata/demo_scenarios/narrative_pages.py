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
"""Check the scenario narrative pages against the registry (DEMOCI-11-012).

A narrative page under ``docs/topics/scenarios/`` describes one demo scenario.
Two things can make such a page lie about the scenario it describes, and neither
is visible from the page itself:

- **The scenario is not in CI.**  Every *registered* scenario is in the
  full-suite matrix on ``main`` (DEMOCI-06-003), so a registered scenario that
  fails is a red workflow run and an auto-filed issue.  A page whose stem names
  no registered scenario describes something no CI run exercises at all.
  :func:`unregistered_narrative_pages` reports it.
- **The page claims an outcome.**  All ten narrative pages once declared
  ``status: stable`` — a template default nothing gated, still present on the
  two pages whose scenarios were failing at the time (ISSUE-3555).  A page
  cannot know whether its scenario passes; the live answer is the
  demo-integration workflow, so a per-item outcome on the page is exactly the
  unverifiable fact MS-16-002 forbids.  :func:`narrative_status_claims`
  reports any such key.

Both are aggregated by :func:`.prose_checks.consistency_problems`, so they reach
``uv run demo-scenarios --check`` (the pre-commit hook) and the unit suite.

Requirements: ``specs/demo-ci.yaml`` DEMOCI-11-003, DEMOCI-11-012;
``specs/meta-specifications.yaml`` MS-16-002.
Guidance: ``notes/demo-scenario-registry.md``.
"""

from __future__ import annotations

from pathlib import Path

from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios
from vultron.metadata.base import repo_root
from vultron.metadata.file_loading import load_frontmatter

#: Repository-relative directory holding the narrative pages (DEMOCI-11-003).
NARRATIVE_DIR = "docs/topics/scenarios"

#: The one page in :data:`NARRATIVE_DIR` that is not a scenario's narrative: it
#: renders the registry's table at build time (DEMOCI-11-009).
NARRATIVE_INDEX = f"{NARRATIVE_DIR}/index.md"

#: Frontmatter keys that state a maturity or outcome for the page's scenario.
#: ``status`` is the spelling the pages actually carried; ``maturity`` is the
#: spelling the release-readiness planning proposed before dropping the idea
#: (ADR-0106).  Checking one spelling would only invite the other.
MATURITY_CLAIM_KEYS: tuple[str, ...] = ("status", "maturity")


def _narrative_dir(base: Path) -> Path:
    """Return the narrative directory, failing if it moved.

    A missing directory is an error, not an empty result: a check that finds no
    pages and reports success would drop every page out of coverage at once
    (DF-09-009).
    """
    directory = base / NARRATIVE_DIR
    if not directory.is_dir():
        raise FileNotFoundError(
            f"{NARRATIVE_DIR} does not exist; the scenario narrative pages are "
            "derived from the registry by convention (DEMOCI-11-003), so update "
            "the convention rather than letting this check skip them"
        )
    return directory


def unregistered_narrative_pages(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> list[str]:
    """Return narrative pages that no registered scenario derives.

    Every ``*.md`` under :data:`NARRATIVE_DIR` other than :data:`NARRATIVE_INDEX`
    must be some registered scenario's ``narrative_path`` (DEMOCI-11-012).  The
    converse — a registered scenario whose page is missing — is
    :func:`.sync.missing_derived_paths`' job (DEMOCI-11-003).

    Raises:
        FileNotFoundError: If :data:`NARRATIVE_DIR` does not exist.
    """
    base = root or repo_root()
    resolved = discover_scenarios() if specs is None else specs
    registered = {spec.narrative_path for spec in resolved}
    return [
        relative
        for page in sorted(_narrative_dir(base).glob("*.md"))
        if (relative := page.relative_to(base).as_posix()) != NARRATIVE_INDEX
        and relative not in registered
    ]


def narrative_status_claims(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> list[str]:
    """Return ``"<page>: <key>"`` for every maturity claim a narrative page makes.

    Checks each registered scenario's narrative page and the index for any key
    in :data:`MATURITY_CLAIM_KEYS` (DEMOCI-11-012).  A registered page that does
    not exist is skipped here because :func:`.sync.missing_derived_paths`
    already reports it; reporting it twice would name the same repair under two
    requirements.

    Raises:
        MetadataLoadError: If a page's frontmatter is malformed (MS-17).
    """
    base = root or repo_root()
    resolved = discover_scenarios() if specs is None else specs
    pages = [spec.narrative_path for spec in resolved]
    pages.append(NARRATIVE_INDEX)
    problems: list[str] = []
    for relative in pages:
        path = base / relative
        if not path.is_file():
            continue
        metadata = load_frontmatter(path, root=base).metadata
        problems.extend(
            f"{relative}: {key}"
            for key in MATURITY_CLAIM_KEYS
            if key in metadata
        )
    return problems


__all__ = [
    "MATURITY_CLAIM_KEYS",
    "NARRATIVE_DIR",
    "NARRATIVE_INDEX",
    "narrative_status_claims",
    "unregistered_narrative_pages",
]
