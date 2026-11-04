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
"""Generate and check the occasion table and its fragments (ADR-0128).

One generator projects the occasions on ``SEMANTIC_REGISTRY`` into committed
artifacts, and ``--check`` fails on any difference (MSM-06-006):

- ``vultron/metadata/msm/occasions.yaml`` — the occasion table, with a
  ``format_version``.  Internal; publication belongs to #2959.
  :func:`~vultron.metadata.msm._mapping.load_occasion_table` loads and
  validates it.
- ``docs/reference/messages/_occasions/lookup.md`` — the whole table, one
  ``##`` group per message page: the case lifecycle first, then protocol
  mechanics.
- ``docs/reference/messages/_occasions/lookup-<page>.md`` — one page's slice.
- ``docs/reference/messages/_occasions/shorthands.md`` — the formal message
  set, each shorthand with the wire activities that carry it, for the
  Protocol Quick Reference (MSM-06-004).
- ``docs/reference/messages/_occasions/sections/<anchor>.md`` — one section
  per occasion, anchored by the occasion's ID: its heading and description,
  then two content tabs, the reference facts and the example JSON.
- ``docs/reference/messages/_occasions/embeds/<anchor>.md`` — one embed per
  occasion: what a page outside the reference includes at the step that sends
  the occasion.  It is a box with no heading, holding the facts a sender acts
  on, a link to the canonical section and the example JSON collapsed, so one
  source renders in two places, separated and linked (DF-01-006, DF-01-007, ADR-0128).

Each section's "Seen in" lists the pages that include its embed.  It is read
from the include directives of every page under ``docs/`` outside the
fragment directory, never typed by hand, and the fragments themselves include
nothing, so the pages that are read are never pages this generator writes:
one ``--write`` settles a new include, and ``--check`` cannot loop.  The
occasion's own message page carries the section, not the embed, so it never
lists itself; no message page may include an embed.  A page the production
build withholds (``draft_docs``, ``exclude_docs``) is not listed, and an embed
must sit on the page a reader sees, not in a fragment another page includes
whole.  An occasion that declares a how-to guide must be embedded there,
which is how the guides are held to show what their steps send.

The table fragments are not named ``*table*.md``: ``lint-docs`` exempts that
name as a generated content class, and these carry occasion prose it must
check (DF-09-007).  Only ``*.md`` files under the fragment directory count as
committed fragments, so ``--write`` never deletes anything else there.

The fragments are rendered from the YAML text, re-parsed, not from the
registry, so the YAML carries every fact a fragment shows.  Every fragment
heading starts at ``##``; a host shifts it with ``heading-offset``.

Links are ordinary relative ``.md`` links, written from the fragment's own
directory.  ``include-markdown`` rewrites them for the host page and MkDocs
then rewrites and checks them as it does any hand-written link.  That is why
these are fragments and not ``markdown_exec`` output, whose links MkDocs never
sees (``vultron/metadata/AGENTS.md`` § Generate vs. Check).  The JSON example
is the exception: it carries no link and its IDs are minted per run, so a
section renders it with an exec block at build time.

The fragments are in ``exclude_docs``: they are not pages of their own.  The
message pages include them, and their links are checked there, against the
host page that carries the sections they point to.  Built alone, a table's
links would be checked against the wrong page, and every fragment would
publish a URL the project then has to keep.

Each section states its entry's mapping status, linked to the definition of
the status values on ``docs/reference/messages/index.md`` (MSM-06-010).  The
table does not carry it: its columns serve a sender choosing what to send, and
the status describes the formal protocol's relation to the wire form.

CLI (``uv run msm-occasions``):
    --check   exit 1 if the YAML or any fragment is stale or unexpected
    --write   rewrite every artifact and delete stale fragments
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from vultron.metadata.base import (
    repo_root,
)
from vultron.metadata.file_loading import (
    MetadataLoadError,
    loads_yaml,
    validate,
)
from vultron.metadata.generated_files import stale_paths, write_generated
from vultron.metadata.msm._mapping import (
    OccasionTable,
    load_occasion_table,
)
from vultron.metadata.msm.occasions.render import (
    render_embed,
    render_section,
    render_shorthands,
    render_slice,
    render_whole,
)
from vultron.metadata.msm.occasions.table import (
    EMBED_DIR,
    FRAGMENT_DIR,
    FRAGMENT_MARKER,
    WRITE_COMMAND,
    YAML_PATH,
    derive_table,
    dump_table,
)
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.semantic_registry._entry import SemanticEntry

# ---------------------------------------------------------------------------
# Artifacts.
# ---------------------------------------------------------------------------


def _fragment(body: str) -> str:
    return f"{FRAGMENT_MARKER}\n\n{body}\n"


def desired_contents(
    root: Path | None = None,
    registry: Sequence[SemanticEntry] = SEMANTIC_REGISTRY,
) -> dict[str, str]:
    """Return ``{repo-relative path: contents}`` for every artifact.

    The fragments are rendered from the YAML text, re-parsed, so a fact the
    YAML does not carry cannot reach a fragment.
    """
    base = root or repo_root()
    text = dump_table(derive_table(registry, base))
    shown = Path(YAML_PATH)
    table = validate(OccasionTable, loads_yaml(text, shown), path=shown)
    contents = {YAML_PATH: text}
    contents[f"{FRAGMENT_DIR}/lookup.md"] = _fragment(render_whole(table))
    contents[f"{FRAGMENT_DIR}/shorthands.md"] = _fragment(
        render_shorthands(table)
    )
    for group in table.groups:
        contents[f"{FRAGMENT_DIR}/lookup-{group.page.value}.md"] = _fragment(
            render_slice(group)
        )
        for row in group.occasions:
            contents[f"{FRAGMENT_DIR}/sections/{row.anchor}.md"] = _fragment(
                render_section(row)
            )
            contents[f"{EMBED_DIR}/{row.anchor}.md"] = _fragment(
                render_embed(group, row)
            )
    return contents


def _committed_fragments(base: Path) -> set[str]:
    directory = base / FRAGMENT_DIR
    if not directory.is_dir():
        return set()
    return {
        path.relative_to(base).as_posix()
        for path in directory.rglob("*.md")
        if path.is_file()
    }


@dataclass(frozen=True)
class Drift:
    """How the committed artifacts differ from a fresh generation.

    Attributes:
        stale: Paths whose contents differ or that are missing.
        unexpected: Files under :data:`FRAGMENT_DIR` that nothing generates.
    """

    stale: tuple[str, ...]
    unexpected: tuple[str, ...]


def _compare(
    base: Path, registry: Sequence[SemanticEntry]
) -> tuple[dict[str, str], Drift]:
    """Generate once and compare; the single comparison point for
    ``--check`` and ``--write``, so the two cannot disagree about "stale"."""
    desired = desired_contents(base, registry)
    stale = tuple(stale_paths(base, desired))
    unexpected = sorted(_committed_fragments(base) - set(desired))
    return desired, Drift(stale=stale, unexpected=tuple(unexpected))


def drift(
    root: Path | None = None,
    registry: Sequence[SemanticEntry] = SEMANTIC_REGISTRY,
) -> Drift:
    """Compare the committed artifacts with a fresh generation."""
    return _compare(root or repo_root(), registry)[1]


def write_artifacts(
    root: Path | None = None,
    registry: Sequence[SemanticEntry] = SEMANTIC_REGISTRY,
) -> list[str]:
    """Rewrite stale artifacts, delete unexpected fragments; return paths."""
    base = root or repo_root()
    desired, found = _compare(base, registry)
    for path in found.stale:
        write_generated(base / path, desired[path])
    for path in found.unexpected:
        (base / path).unlink()
    return [*found.stale, *found.unexpected]


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: ``uv run msm-occasions [--check|--write]``."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the occasion table or any fragment is stale.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Rewrite the occasion table and every fragment.",
    )
    args = parser.parse_args(argv)
    root = repo_root()

    if args.write:
        written = write_artifacts(root)
        if not written:
            print("Occasion artifacts already in sync.")
        for path in written:
            print(f"Wrote {path}")
        return

    found = drift(root)
    problems: list[str] = []
    # A committed table that is not stale is byte-for-byte the text
    # desired_contents just generated and validated, so loading it again
    # could only repeat that verdict at the cost of two more YAML parses.
    if YAML_PATH in found.stale:
        try:
            load_occasion_table(root / YAML_PATH, root=root)
        except FileNotFoundError:
            pass  # reported as stale below
        except MetadataLoadError as exc:
            problems.append(str(exc))
    problems.extend(
        f"{path} is stale — run '{WRITE_COMMAND}' (MSM-06-006)."
        for path in found.stale
    )
    problems.extend(
        f"{path} is not generated from any occasion — run "
        f"'{WRITE_COMMAND}' to delete it (MSM-06-006)."
        for path in found.unexpected
    )
    if problems:
        for problem in problems:
            print(f"[ERROR] {problem}", file=sys.stderr)
        sys.exit(1)
    print("Occasion artifacts are in sync.")
