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

Three artifacts are generated from the scenario registry and committed:

- ``.github/demo-scenarios.json`` — whole file. It stays committed because the
  ``scenarios`` job in ``demo-integration.yml`` resolves the CI matrix with
  ``jq`` immediately after checkout, in a job with no Python environment.
- ``test/ci/README-case-log-ratchet.md`` — the table between the markers.
- ``vultron/demo/scenario/README.md`` — the table between the markers.

Both markdown files sit outside the MkDocs tree, so they cannot use
``{% include-markdown %}``: the directive expands only at mkdocs build time and
would render literally to every reader (DEMOCI-11-006).  Generated-between-
markers is the treatment for that case;
``docs/topics/scenarios/index.md`` is inside the tree and renders at build time
instead, committing no table at all (DEMOCI-11-009).

``--check`` is wired into pre-commit as ``demo-scenarios-sync``, exactly as
``docs/adr/index.md`` is gated by ``adr-index-sync``.  It also reports the
*checked* consumers — the ``mkdocs.yml`` nav, the ``notes/`` scenario tables,
the planned-scenario register and restated counts — from
:mod:`vultron.metadata.demo_scenarios.prose_checks`, so one command covers both
halves of ADR-0098's generate-vs-check split.  Those findings are reported only:
``--write`` cannot fix prose.

CLI (``uv run demo-scenarios``):
    --check   exit 1 if any committed artifact is stale
    --write   rewrite every committed artifact in place
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from vultron.demo.scenario.registry import (
    ScenarioSpec,
    discover_scenarios,
)
from vultron.metadata.base import repo_root
from vultron.metadata.demo_scenarios.prose_checks import consistency_problems
from vultron.metadata.demo_scenarios.render import (
    render_page,
    scenario_matrix_json,
)

#: Command that regenerates every artifact, quoted in every failure message.
WRITE_COMMAND = "uv run demo-scenarios --write"

#: Opening marker of a generated table. Carries the regeneration command so a
#: reader who found the table by grep, not by reading this module, still learns
#: that hand-editing it will be reverted.
BEGIN_MARKER = (
    "<!-- BEGIN GENERATED SCENARIO TABLE — do not edit; "
    f"edit the @scenario decorators and run `{WRITE_COMMAND}` -->"
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
    for marker, label in ((BEGIN_MARKER, "begin"), (END_MARKER, "end")):
        count = current.count(marker)
        if count != 1:
            raise ValueError(
                f"{path}: found {count} generated-table {label} markers, "
                f"expected exactly 1. The marker text is:\n  {marker}"
            )
    start = current.index(BEGIN_MARKER)
    end = current.index(END_MARKER)
    if end < start:
        raise ValueError(
            f"{path}: the generated-table end marker precedes the begin marker"
        )
    head = current[: start + len(BEGIN_MARKER)]
    tail = current[end:]
    return f"{head}\n\n{body}\n\n{tail}"


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
    _marker_artifact(HARNESS_README, "harnesses"),
    _marker_artifact(SCENARIO_README, "subcommands"),
)


def desired_contents(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> dict[str, str]:
    """Return ``{repo-relative path: desired full contents}`` for every artifact.

    Args:
        root: Repository root. Defaults to the enclosing checkout.
        specs: Scenarios to render. Defaults to the discovered registry.

    Raises:
        FileNotFoundError: If a marker-block artifact does not exist. Its
            hand-written prose cannot be reconstructed, so there is nothing to
            splice into.
        ValueError: If a marker-block artifact's markers are missing or
            malformed.
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
    out_of_date: list[tuple[Path, str, str]] = []
    for path, desired in desired_contents(base, specs).items():
        target = base / path
        current = (
            target.read_text(encoding="utf-8") if target.is_file() else ""
        )
        if current != desired:
            out_of_date.append((target, path, desired))
    return out_of_date


def stale_artifacts(
    root: Path | None = None,
    specs: tuple[ScenarioSpec, ...] | None = None,
) -> list[str]:
    """Return the repo-relative paths whose committed contents are stale."""
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
    """Rewrite every stale artifact in place; return the paths written."""
    base = root or repo_root()
    written: list[str] = []
    for target, path, desired in _out_of_date(base, specs):
        # A whole-file artifact can legitimately not exist yet, and in a
        # caller-supplied root its parent directory may not either.
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(desired, encoding="utf-8")
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
