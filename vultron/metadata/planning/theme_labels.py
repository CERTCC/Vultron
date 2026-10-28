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
"""Sync GitHub's ``theme:`` labels from the theme catalog (``theme-labels``).

Requirements: PAD-02-019 to PAD-02-021.

::

    theme-labels            # report drift; change nothing (exit 1 on drift)
    theme-labels --apply    # create and update labels to match the catalog
    theme-labels --json     # the drift as JSON

Drift has three parts. A catalog theme with no GitHub label is **missing** and
``--apply`` creates it. A label whose description or color differs from its
entry is **changed** and ``--apply`` edits it. A ``theme:`` label on GitHub that
the catalog does not list is **unlisted**: it is reported and never deleted,
because removing a label strips it from every Issue that carries it, and only a
person can decide that.

:func:`compute_drift` is pure, so the tests pin it without the network; the
``gh`` calls go through an injectable runner.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.planning.themes import (
    THEME_PREFIX,
    Theme,
    ThemeCatalog,
    load_theme_catalog,
)

DEFAULT_REPO = "CERTCC/Vultron"

Runner = Callable[[Sequence[str]], str]
"""Runs a ``gh`` argument list and returns its standard output."""


@dataclass(frozen=True)
class RemoteLabel:
    """A label as GitHub reports it."""

    name: str
    description: str
    color: str


@dataclass(frozen=True)
class LabelChange:
    """A catalog theme whose GitHub label differs from its entry."""

    theme: Theme
    remote: RemoteLabel

    def differences(self) -> tuple[tuple[str, str, str], ...]:
        """Each differing field as ``(name, GitHub value, catalog value)``.

        Colors compare case-insensitively: GitHub reports them in lower case.
        """
        differ: list[tuple[str, str, str]] = []
        if self.remote.description != self.theme.description:
            differ.append(
                (
                    "description",
                    self.remote.description,
                    self.theme.description,
                )
            )
        if self.remote.color.upper() != self.theme.color:
            differ.append(("color", self.remote.color, self.theme.color))
        return tuple(differ)

    def fields(self) -> tuple[str, ...]:
        """The names of the fields that differ."""
        return tuple(name for name, _, _ in self.differences())


@dataclass(frozen=True)
class LabelDrift:
    """What differs between the catalog and GitHub's ``theme:`` labels."""

    missing: tuple[Theme, ...]
    changed: tuple[LabelChange, ...]
    unlisted: tuple[RemoteLabel, ...]

    @property
    def in_sync(self) -> bool:
        """True when GitHub matches the catalog exactly."""
        return not (self.missing or self.changed or self.unlisted)

    def to_json(self) -> dict[str, object]:
        """The drift as a JSON-ready mapping."""
        return {
            "missing": [t.label for t in self.missing],
            "changed": [
                {"label": c.theme.label, "fields": list(c.fields())}
                for c in self.changed
            ],
            "unlisted": [r.name for r in self.unlisted],
            "in_sync": self.in_sync,
        }


def compute_drift(
    catalog: ThemeCatalog, remote: Iterable[RemoteLabel]
) -> LabelDrift:
    """Compare *catalog* with GitHub's labels.

    Args:
        catalog: The theme catalog.
        remote: Every label on the repository; non-theme labels are ignored.
    """
    themed = {r.name: r for r in remote if r.name.startswith(THEME_PREFIX)}
    missing: list[Theme] = []
    changed: list[LabelChange] = []
    for theme in catalog.themes:
        found = themed.get(theme.label)
        if found is None:
            missing.append(theme)
            continue
        change = LabelChange(theme=theme, remote=found)
        if change.fields():
            changed.append(change)
    labels = catalog.labels()
    unlisted = sorted(
        (r for name, r in themed.items() if name not in labels),
        key=lambda r: r.name,
    )
    return LabelDrift(tuple(missing), tuple(changed), tuple(unlisted))


def format_drift(drift: LabelDrift) -> str:
    """A human-readable drift report."""
    if drift.in_sync:
        return "theme labels match the catalog."
    out: list[str] = []
    for theme in drift.missing:
        out.append(f"missing   {theme.label} (create)")
    for change in drift.changed:
        out.append(
            f"changed   {change.theme.label} "
            f"({', '.join(change.fields())}; update)"
        )
        for name, was, now in change.differences():
            out.append(f"            {name}: {was!r} -> {now!r}")
    for label in drift.unlisted:
        out.append(
            f"unlisted  {label.name} (not in the catalog; not deleted — "
            f"add it to the catalog or retire it by hand)"
        )
    return "\n".join(out)


def _gh(args: Sequence[str]) -> str:
    """Run ``gh`` and return its standard output; raise on failure."""
    return subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True
    ).stdout


def fetch_labels(repo: str, run: Runner = _gh) -> tuple[RemoteLabel, ...]:
    """Every label on *repo*, as GitHub reports it."""
    raw = run(
        [
            "label",
            "list",
            "--repo",
            repo,
            "--limit",
            "1000",
            "--json",
            "name,description,color",
        ]
    )
    return tuple(
        RemoteLabel(
            name=item["name"],
            description=item.get("description") or "",
            color=item.get("color") or "",
        )
        for item in json.loads(raw)
    )


def apply_drift(drift: LabelDrift, repo: str, run: Runner = _gh) -> None:
    """Create the missing labels and edit the changed ones.

    Unlisted labels are left untouched (PAD-02-020).
    """
    for theme in drift.missing:
        run(
            [
                "label",
                "create",
                theme.label,
                "--repo",
                repo,
                "--color",
                theme.color,
                "--description",
                theme.description,
            ]
        )
    for change in drift.changed:
        theme = change.theme
        run(
            [
                "label",
                "edit",
                theme.label,
                "--repo",
                repo,
                "--color",
                theme.color,
                "--description",
                theme.description,
            ]
        )


def main(argv: list[str] | None = None, run: Runner = _gh) -> int:
    """CLI entry point: report or apply ``theme:`` label drift.

    Returns 0 when GitHub matches the catalog (after ``--apply``'s changes,
    when given), 1 while drift remains, and 2 when the catalog cannot be
    loaded or a ``gh`` call fails. Unlisted labels survive ``--apply``, so
    they keep the exit at 1 until a person resolves them.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Sync GitHub theme: labels from the catalog in "
            "notes/epic-themes.md. Reports drift by default; never deletes."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="create missing labels and update changed ones",
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help="OWNER/NAME (default: %(default)s)",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        help="the catalog note (default: notes/epic-themes.md)",
    )
    parser.add_argument(
        "--json", action="store_true", help="print the drift as JSON"
    )
    args = parser.parse_args(argv)

    try:
        catalog = load_theme_catalog(args.catalog)
        drift = compute_drift(catalog, fetch_labels(args.repo, run))
    except MetadataLoadError as exc:
        print(f"theme-labels: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"theme-labels: gh failed: {exc.stderr}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(drift.to_json(), indent=2))
    else:
        print(format_drift(drift))

    if not args.apply:
        return 0 if drift.in_sync else 1
    try:
        apply_drift(drift, args.repo, run)
    except subprocess.CalledProcessError as exc:
        print(f"theme-labels: gh failed: {exc.stderr}", file=sys.stderr)
        return 2
    applied = len(drift.missing) + len(drift.changed)
    print(f"applied {applied} label change(s).")
    return 1 if drift.unlisted else 0


if __name__ == "__main__":
    sys.exit(main())
