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
"""Generate and check the committed demo scenario artifacts (DEMOCI-11-005).

These artifacts are generated from the scenario registry and committed:

- ``.github/demo-scenarios.json`` — whole file. It stays committed because the
  ``scenarios`` job in ``demo-integration.yml`` resolves the CI matrix with
  ``jq`` immediately after checkout, in a job with no Python environment.
- ``vultron/demo/scenario/plots.json`` — whole file: every scenario's
  flattened story, so a reordered fragment fails this check instead of
  surfacing on the next recordings run (:mod:`.plots`, DEMOCI-11-034,
  DEMOCI-11-035).
- ``test/ci/README-case-log-ratchet.md`` — the table between the markers.
- ``vultron/demo/scenario/README.md`` — the table between the markers.
- ``docs/topics/scenarios/_<scenario>-story.md`` — whole file, one per
  registered scenario: the same plot rendered as a numbered story in domain
  terms, included by that scenario's narrative page (:mod:`.stories`,
  DEMOCI-11-067, DEMOCI-11-069). This is the one set whose *membership*
  comes from the registry rather than from a declaration, so it is added to
  :func:`desired_contents` beside :data:`ARTIFACTS` rather than listed in it.

Both markdown files sit outside the MkDocs tree, so they cannot use
``{% include-markdown %}``: the directive expands only at mkdocs build time and
would render literally to every reader (DEMOCI-11-006).  Generated-between-
markers is the treatment for that case;
``docs/topics/scenarios/index.md`` is inside the tree and renders at build time
instead, committing no table at all (DEMOCI-11-009).

``--check`` is wired into pre-commit as ``demo-scenarios-sync``, exactly as
``docs/adr/index.md`` is gated by ``adr-index-sync``.  It also reports the
*checked* consumers — the ``mkdocs.yml`` nav, the ``notes/`` scenario tables and
their harness-derived semantic-type columns, the DEMOCI-06-002/003 spec
enumerations, the planned-scenario register, restated counts and stray include
directives — via :func:`prose_checks.consistency_problems`, so one command covers
both halves of ADR-0098's generate-vs-check split.  Those findings are reported
only: ``--write`` cannot fix prose.

Anything ``consistency_problems`` does not aggregate is *not* covered by the
hook, whatever a pytest module also asserts about it.  Keep the two in step: a
check that exists only as a test lets a stale artifact through the hook and fails
later in CI, which is the gap ISSUE-3451 left on DEMOCI-06-003.

CLI (``uv run demo-scenarios``):
    --check   exit 1 if any committed artifact is stale
    --write   rewrite every committed artifact in place
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from vultron.demo.scenario.registry import (
    ScenarioSpec,
    discover_scenarios,
)
from vultron.metadata.base import repo_root
from vultron.metadata.demo_scenarios.plots import (
    PLOT_MANIFEST,
    plot_manifest_json,
)
from vultron.metadata.demo_scenarios.prose_checks import consistency_problems
from vultron.metadata.demo_scenarios.render import (
    render_page,
    scenario_matrix_json,
)
from vultron.metadata.demo_scenarios.stories import story_fragments
from vultron.metadata.generated_block import splice_between
from vultron.metadata.generated_files import stale_paths, write_generated

#: Command that regenerates every artifact, quoted in every failure message.
WRITE_COMMAND = "uv run demo-scenarios --write"

#: Opening marker of a generated table. Carries the regeneration command so a
#: reader who found the table by grep, not by reading this module, still learns
#: that hand-editing it will be reverted. Two lines, so neither runs past the
#: 88-character Markdown limit (PD-10-001).
BEGIN_MARKER = (
    "<!-- BEGIN GENERATED SCENARIO TABLE — do not edit; edit the @scenario\n"
    f"     decorators and run `{WRITE_COMMAND}` -->"
)

#: Closing marker of a generated table.
END_MARKER = "<!-- END GENERATED SCENARIO TABLE -->"

MATRIX_JSON = ".github/demo-scenarios.json"
HARNESS_README = "test/ci/README-case-log-ratchet.md"
SCENARIO_README = "vultron/demo/scenario/README.md"


@dataclass(frozen=True, slots=True)
class Artifact:
    """One committed artifact generated from the scenario registry.

    Attributes:
        path: Repository-relative path.
        desired: Renders the artifact's desired full contents from the registry
            and the file's current contents (the latter matters only for
            marker-block artifacts, whose hand-written prose is preserved).
        whole_file: Whether the artifact is generated in its entirety, and so
            can be created from nothing. A marker-block artifact cannot: its
            surrounding prose is hand-written and unreconstructable, so an
            absent file is an error rather than something to write. Declared as
            a field rather than inferred from ``path`` so that adding a second
            whole-file artifact does not silently become unwritable.
    """

    path: str
    desired: Callable[[tuple[ScenarioSpec, ...], str], str]
    whole_file: bool = False


def splice(current: str, body: str, path: str) -> str:
    """Return *current* with the text between the markers replaced by *body*.

    Args:
        current: Current file contents.
        body: Generated markdown to place between the markers.
        path: Repository-relative path, for error attribution.

    Raises:
        ValueError: If the marker pair is missing, duplicated, or inverted.
            Silently appending a table when the markers are absent would leave
            the stale copy in place above the new one, so this fails instead.
    """
    return splice_between(current, body, path, BEGIN_MARKER, END_MARKER)


def _marker_artifact(path: str, slug: str) -> Artifact:
    """Build an :class:`Artifact` that splices *slug*'s table into *path*."""

    def desired(specs: tuple[ScenarioSpec, ...], current: str) -> str:
        return splice(current, render_page(slug, specs), path)

    return Artifact(path=path, desired=desired)


#: Every committed artifact, in reporting order.
ARTIFACTS: tuple[Artifact, ...] = (
    Artifact(
        path=MATRIX_JSON,
        desired=lambda specs, _current: scenario_matrix_json(specs),
        whole_file=True,
    ),
    Artifact(
        path=PLOT_MANIFEST,
        desired=lambda specs, _current: plot_manifest_json(
            specs, WRITE_COMMAND
        ),
        whole_file=True,
    ),
    _marker_artifact(HARNESS_README, "harnesses"),
    _marker_artifact(SCENARIO_README, "subcommands"),
)


def desired_contents(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> dict[str, str]:
    """Return ``{repo-relative path: desired full contents}`` for every artifact.

    The declared artifacts first, in :data:`ARTIFACTS` order, then one
    generated story per registered scenario (:mod:`.stories`).

    Args:
        root: Repository root. Defaults to the enclosing checkout.
        specs: Scenarios to render. Defaults to the discovered registry.

    Raises:
        FileNotFoundError: If a marker-block artifact does not exist. Its
            hand-written prose cannot be reconstructed, so there is nothing to
            splice into.
        ValueError: If a marker-block artifact's markers are missing or
            malformed.
        DemoStoryError: If a story holds an item the plot manifest cannot
            name (:mod:`.plots`, DEMOCI-11-034), or a fragment whose docstring
            does not open with one sentence in domain terms (:mod:`.stories`,
            DEMOCI-11-065). It is raised from the demo
            layer and left to propagate as a traceback, from here through
            :func:`stale_artifacts`, :func:`write_artifacts` and
            :func:`main`: neither ``--check`` nor ``--write`` can say
            anything about a manifest that cannot be rendered at all, and
            this module may not catch it by name — ``vultron/metadata/``
            raises and handles no ``VultronError`` (MS-17-006), and a
            blanket ``except`` is forbidden (CS-23-001). The demo layer's
            message names the scenario, the item and the remedy, and the
            traceback adds the source of the fragment.
    """
    base = root or repo_root()
    resolved = discover_scenarios() if specs is None else specs

    contents: dict[str, str] = {}
    for artifact in ARTIFACTS:
        target = base / artifact.path
        current = (
            target.read_text(encoding="utf-8") if target.is_file() else ""
        )
        if not current and not artifact.whole_file:
            raise FileNotFoundError(
                f"{artifact.path} is missing or empty; its generated table is "
                "spliced between markers in hand-written prose that cannot be "
                "regenerated. Restore the file, then run "
                f"'{WRITE_COMMAND}'."
            )
        contents[artifact.path] = artifact.desired(resolved, current)
    contents.update(story_fragments(resolved, WRITE_COMMAND))
    return contents


def _out_of_date(
    base: Path,
    specs: tuple[ScenarioSpec, ...] | None,
) -> list[tuple[Path, str, str]]:
    """Return ``(target, path, desired)`` for each artifact whose contents differ.

    The single comparison point for both ``--check`` and ``--write``, so the two
    modes cannot disagree about what "stale" means — a hook that reported stale
    while the writer found nothing to do would be unfixable by the command its
    own error message names.
    """
    desired = desired_contents(base, specs)
    return [
        (base / path, path, desired[path])
        for path in stale_paths(base, desired)
    ]


def stale_artifacts(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> list[str]:
    """Return the repo-relative paths whose committed contents are stale.

    Raises:
        FileNotFoundError, ValueError, DemoStoryError: As
            :func:`desired_contents`.
    """
    base = root or repo_root()
    return [path for _target, path, _desired in _out_of_date(base, specs)]


def missing_derived_paths(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> list[str]:
    """Return ``"<scenario>: <path>"`` for every derived path that does not exist.

    Checked here as well as in the test suite because this is the earliest gate:
    a registered scenario whose harness file is absent would otherwise be
    written straight into the CI matrix, where the failure surfaces as a red
    demo job rather than as the naming mistake it is (DEMOCI-11-003).
    """
    base = root or repo_root()
    resolved = discover_scenarios() if specs is None else specs
    return [
        f"{spec.name}: {path}"
        for spec in resolved
        for path in spec.derived_paths
        if not (base / path).exists()
    ]


def write_artifacts(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> list[str]:
    """Rewrite every stale artifact in place; return the paths written.

    Raises:
        FileNotFoundError, ValueError, DemoStoryError: As
            :func:`desired_contents`.
    """
    base = root or repo_root()
    written: list[str] = []
    for target, path, desired in _out_of_date(base, specs):
        # A whole-file artifact can legitimately not exist yet, and in a
        # caller-supplied root its parent directory may not either;
        # write_generated creates it.
        write_generated(target, desired)
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: ``uv run demo-scenarios [--check|--write]``."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if any committed scenario artifact is stale.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Rewrite every committed scenario artifact.",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    specs = discover_scenarios()

    problems = [
        f"registered scenario names a path that does not exist — {entry} "
        "(DEMOCI-11-003). Rename the file to match the scenario name, or fix "
        "the name in the @scenario decorator."
        for entry in missing_derived_paths(root, specs)
    ]

    if args.write:
        if problems:
            for problem in problems:
                print(f"[ERROR] {problem}", file=sys.stderr)
            sys.exit(1)
        written = write_artifacts(root, specs)
        if not written:
            print("Demo scenario artifacts already in sync.")
            return
        for path in written:
            print(f"Wrote {path}")
        return

    # --check
    #
    # An empty registry is reported as its own failure rather than as a clean
    # tree: every per-scenario artifact, including each narrative page's
    # generated story, would then be checked against nothing and the gate
    # would pass over the whole set (DF-09-009). Discovery is a pkgutil walk
    # (DEMOCI-11-002), so an empty result means the walk imported nothing.
    if not specs:
        problems.append(
            "the scenario registry is empty, so this gate compared no "
            "scenario's artifacts with anything; an empty target set is a "
            "failure, not a pass (DF-09-009). Check that the scenario "
            "modules under vultron/demo/scenario/ still import "
            "(DEMOCI-11-002)."
        )
    #
    # Only name --write as the remedy when it would actually run: it
    # short-circuits on any missing derived path and writes nothing, so
    # pointing at it while a path problem is outstanding sends the developer to
    # a command that cannot make progress. Fix the path first, then regenerate.
    remedy = (
        f"run '{WRITE_COMMAND}'"
        if not problems
        else "fix the derived path above first, then regenerate"
    )
    problems.extend(
        f"{path} is stale — {remedy} (DEMOCI-11-005)."
        for path in stale_artifacts(root, specs)
    )
    # The checked half of the generate-vs-check split (ADR-0098). Reported by
    # the same command as the generated half so the hook that names one names
    # both; --write cannot fix these, which is why they are --check-only.
    problems.extend(consistency_problems(root, specs))
    if problems:
        for problem in problems:
            print(f"[ERROR] {problem}", file=sys.stderr)
        sys.exit(1)
    print(
        f"Demo scenario artifacts are in sync ({len(specs)} scenarios "
        "registered)."
    )


if __name__ == "__main__":
    main()


__all__ = [
    "ARTIFACTS",
    "BEGIN_MARKER",
    "END_MARKER",
    "HARNESS_README",
    "MATRIX_JSON",
    "PLOT_MANIFEST",
    "SCENARIO_README",
    "WRITE_COMMAND",
    "Artifact",
    "desired_contents",
    "main",
    "missing_derived_paths",
    "splice",
    "stale_artifacts",
    "write_artifacts",
]
