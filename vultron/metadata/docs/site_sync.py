"""Generate and check the committed docs-site artifacts (DF-11-005/008/011).

Three kinds of artifact are generated and committed:

- each top-level section **landing page** under ``docs/`` — only the contents
  listing between the markers, so the hand-written framing survives
  (:mod:`~vultron.metadata.docs.landing_pages`);
- ``docs/includes/stakeholder_types.md`` — whole file, from the schema
  (:mod:`~vultron.metadata.docs.stakeholder_fragment`);
- ``notes/site-coverage-matrix.md`` — whole file, from page frontmatter
  (:mod:`~vultron.metadata.docs.coverage_matrix`).

``--check`` is wired into pre-commit as ``docs-site-sync``;
``test_committed_site_artifacts_are_in_sync`` enforces it in CI and is the
backstop for a deletion, which pre-commit's staged-file list cannot match. Both
modes compare through :func:`_out_of_date`, so they cannot disagree about what
"stale" means.

CLI (``uv run docs-site``):
    --check   exit 1 if any committed artifact is stale
    --write   rewrite every committed artifact in place
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vultron.metadata.base import repo_root
from vultron.metadata.docs.coverage_matrix import (
    MATRIX_PATH,
    measure_coverage,
    render_matrix,
)
from vultron.metadata.docs.landing_pages import (
    WRITE_COMMAND,
    discover_landing_pages,
    splice_listing,
)
from vultron.metadata.docs.stakeholder_fragment import (
    FRAGMENT_PATH,
    render_fragment,
)
from vultron.metadata.file_loading import MetadataLoadError


def _read(target: Path) -> str:
    return target.read_text(encoding="utf-8") if target.is_file() else ""


def desired_contents(root: Path) -> dict[str, str]:
    """Return ``{repo-relative path: desired full contents}`` for every artifact.

    Raises:
        FileNotFoundError: If a landing page is missing or empty; its
            hand-written prose cannot be regenerated.
        MetadataLoadError: If a listed page is missing or unreadable, a
            page's declarations do not validate, or a target set is empty
            (DF-09-009).
        ValueError: If a landing page's markers are missing or malformed.
    """
    contents = {
        FRAGMENT_PATH: render_fragment(),
        MATRIX_PATH: render_matrix(measure_coverage(root)),
    }
    for page in discover_landing_pages(root):
        path = f"docs/{page.path}"
        current = _read(root / path)
        if not current:
            raise FileNotFoundError(
                f"{path} is missing or empty; its generated listing is spliced "
                "between markers in hand-written prose that cannot be "
                f"regenerated. Restore the file, then run '{WRITE_COMMAND}'."
            )
        contents[path] = splice_listing(current, page)
    return contents


def _out_of_date(root: Path) -> list[tuple[Path, str, str]]:
    """Return ``(target, path, desired)`` for each artifact whose contents differ."""
    stale: list[tuple[Path, str, str]] = []
    for path, desired in desired_contents(root).items():
        target = root / path
        if _read(target) != desired:
            stale.append((target, path, desired))
    return stale


def stale_artifacts(root: Path | None = None) -> list[str]:
    """Return the repo-relative paths whose committed contents are stale."""
    return [path for _t, path, _d in _out_of_date(root or repo_root())]


def write_artifacts(root: Path | None = None) -> list[str]:
    """Rewrite every stale artifact in place; return the paths written.

    One pass is enough: no artifact declares a ``level`` or
    ``stakeholder_type``, so writing one never changes what the coverage
    matrix counts.
    """
    written: list[str] = []
    for target, path, desired in _out_of_date(root or repo_root()):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(desired, encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: ``uv run docs-site [--check|--write]``."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if any committed docs-site artifact is stale.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Rewrite every committed docs-site artifact.",
    )
    args = parser.parse_args(argv)
    root = repo_root()
    try:
        if args.write:
            written = write_artifacts(root)
            for path in written:
                print(f"Wrote {path}")
            if not written:
                print("Docs-site artifacts already in sync.")
            return
        stale = stale_artifacts(root)
    except (MetadataLoadError, OSError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    if stale:
        for path in stale:
            print(
                f"[ERROR] {path} is stale — run '{WRITE_COMMAND}' (DF-11-005).",
                file=sys.stderr,
            )
        sys.exit(1)
    print("Docs-site artifacts are in sync.")


if __name__ == "__main__":
    main()
