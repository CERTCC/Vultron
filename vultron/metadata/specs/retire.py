"""Retired-requirement archive and the ``spec-retire`` helper.

A requirement is removed from ``specs/`` rather than marked deprecated
(MS-09-001).
Its last published text is kept, one file per ID, in
``plan/retired-specs/`` (MS-09-005) so a citation of the ID still resolves to
something, while the retired text stays out of every spec loader and out of
agent context (MS-09-009).
An ID in the archive is never reused (MS-09-004).

Usage::

    uv run spec-retire <ID> --why "..." --by "#N" \
        [--replacement <NEW-ID>] [--base REF]

The helper removes the item from its spec file, archives its last published
text, records the removal in the implementation history (MS-09-002), and lists
every remaining cross-reference that MS-09-003 requires repointing.

The archived text is the item's block at the merge base of the base branch and
``HEAD`` (MS-09-008), not the working tree: a branch that edits a requirement
and then retires it must not archive text that was never published. The base
branch is the growth guards' (``origin/$GITHUB_BASE_REF``, else
``origin/main``) unless ``--base`` names another. An item absent at that base,
or a base that cannot be resolved, is refused with nothing changed.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import re
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from vultron.metadata.base import repo_root as _repo_root
from vultron.metadata.history.cli import _build_content, append_history_entry
from vultron.metadata.history.types import HistoryEntryType
from vultron.metadata.specs.growth_guard import (
    BaseUnavailableError,
    base_ref_name,
    materialize_tree,
    resolve_merge_base,
)
from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.schema import SPEC_ID_PATTERN

logger = logging.getLogger(__name__)

#: Archive location relative to the repository root (MS-09-005).
RETIRED_SPECS_RELPATH = Path("plan") / "retired-specs"

_README = "README.md"
#: A whole requirement ID, with its optional sub-item letter (MS-04-001).
_SPEC_ID_RE = re.compile(rf"^{SPEC_ID_PATTERN}$")

#: Trees whose mentions of a retired ID are history or the archive itself and
#: so are never repointed.
_XREF_EXCLUDED_PREFIXES = ("plan/retired-specs/", "plan/history/")


class RetireError(Exception):
    """A requirement could not be retired; the message says why."""


def retired_specs_dir(repo_root: Path) -> Path:
    return repo_root / RETIRED_SPECS_RELPATH


def retired_spec_ids(repo_root: Path) -> frozenset[str]:
    """Return every requirement ID in the archive under *repo_root*.

    An archive file is named ``<ID>.md``; the folder's ``README.md`` is not an
    entry.
    A missing folder is an empty archive.
    """
    archive = retired_specs_dir(repo_root)
    if not archive.is_dir():
        return frozenset()
    return frozenset(p.stem for p in archive.glob("*.md") if p.name != _README)


@dataclass(frozen=True)
class _Block:
    """The line span of one spec item within a spec file."""

    start: int
    end: int  # exclusive

    def slice(self, lines: list[str]) -> list[str]:
        return lines[self.start : self.end]


def _find_block(lines: list[str], spec_id: str) -> _Block | None:
    """Locate the ``- id: <spec_id>`` list item and its continuation lines."""
    head = re.compile(
        rf"^(\s*)- id:\s*['\"]?{re.escape(spec_id)}['\"]?\s*(#.*)?$"
    )
    for i, line in enumerate(lines):
        m = head.match(line)
        if m is None:
            continue
        indent = len(m.group(1))
        end = i + 1
        while end < len(lines):
            nxt = lines[end]
            if nxt.strip() and (len(nxt) - len(nxt.lstrip())) <= indent:
                break
            end += 1
        while end > i + 1 and not lines[end - 1].strip():
            end -= 1
        return _Block(i, end)
    return None


def _find_in_dir(
    spec_dir: Path, spec_id: str
) -> tuple[Path, list[str], _Block] | None:
    """The spec file under *spec_dir* declaring *spec_id*, if any."""
    for path in sorted(spec_dir.glob("*.yaml")):
        lines = path.read_text(encoding="utf-8").splitlines()
        block = _find_block(lines, spec_id)
        if block is not None:
            return path, lines, block
    return None


def _locate(spec_dir: Path, spec_id: str) -> tuple[Path, list[str], _Block]:
    found = _find_in_dir(spec_dir, spec_id)
    if found is None:
        raise RetireError(
            f"{spec_id} is not declared in any {spec_dir}/*.yaml"
        )
    return found


@dataclass(frozen=True)
class PublishedText:
    """An item's block as the base branch has it.

    Attributes:
        base: The merge-base commit the block was read at.
        text: The block, one string, without a trailing newline.
    """

    base: str
    text: str


def published_text(
    root: Path, spec_id: str, base_ref: str | None = None
) -> PublishedText:
    """Return *spec_id*'s block at the merge base of *base_ref* and ``HEAD``.

    *base_ref* defaults to the growth guards' base branch
    (:func:`~vultron.metadata.specs.growth_guard.base_ref_name`).

    Raises:
        RetireError: The base cannot be resolved or read, or *spec_id* is not
            declared in ``specs/`` there (it was added on this branch, so it
            was never published).
    """
    ref = base_ref or base_ref_name()
    try:
        base = resolve_merge_base(root, ref)
        with tempfile.TemporaryDirectory(prefix="spec-retire-") as tmp:
            materialize_tree(root, base, ["specs"], Path(tmp))
            found = _find_in_dir(Path(tmp) / "specs", spec_id)
    except (
        BaseUnavailableError,
        OSError,
        tarfile.TarError,
        UnicodeDecodeError,
    ) as exc:
        raise RetireError(
            f"cannot read the published text of {spec_id}: {exc}; "
            f"pass --base to name the branch it was published on"
        ) from exc
    if found is None:
        raise RetireError(
            f"{spec_id} is not declared at the merge base {base[:12]} of "
            f"{ref}, so it was never published there: delete it from "
            f"specs/ instead of retiring it, or pass --base to name the "
            f"branch it was published on"
        )
    _, lines, block = found
    return PublishedText(base, "\n".join(block.slice(lines)))


def render_archive_entry(
    spec_id: str,
    *,
    retired_on: datetime.date,
    retired_by: str,
    why: str,
    replacement: str | None,
    last_text: str,
) -> str:
    """Render an archive file in the layout the hand-written entries use."""
    lines = [
        f"# {spec_id} (retired)",
        "",
        f"- **Retired**: {retired_on.isoformat()} ({retired_by})",
    ]
    if replacement:
        lines.append(f"- **Replacement**: {replacement}")
    lines += [
        f"- **Why**: {why.strip()}",
        "- **Last text**:",
        "",
        "```yaml",
        last_text.rstrip("\n"),
        "```",
        "",
    ]
    return "\n".join(lines)


def find_cross_references(
    repo_root: Path, spec_id: str
) -> list[tuple[str, int, str]]:
    """List ``(path, line_no, line)`` for each remaining mention of *spec_id*.

    These are the citations MS-09-003 requires repointing.
    The archive and the history are excluded: they record what was true then.
    """
    listing = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    # A trailing digit or sub-item letter makes another ID: retiring
    # ``PREFIX-NN-NNN`` must not list a citation of ``PREFIX-NN-NNNb``.
    pattern = re.compile(rf"(?<![A-Za-z0-9-]){re.escape(spec_id)}(?![0-9a-z])")
    hits: list[tuple[str, int, str]] = []
    for rel in listing.split("\0"):
        if not rel or rel.startswith(_XREF_EXCLUDED_PREFIXES):
            continue
        try:
            text = (repo_root / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                hits.append((rel, n, line.strip()))
    return hits


def _validate_request(
    root: Path, spec_id: str, why: str, replacement: str | None
) -> None:
    if not _SPEC_ID_RE.match(spec_id):
        raise RetireError(f"{spec_id!r} is not a requirement ID")
    if not why.strip():
        raise RetireError("--why must say why the requirement was removed")
    if spec_id in retired_spec_ids(root):
        raise RetireError(f"{spec_id} is already in the archive (MS-09-004)")
    if replacement is None:
        return
    if not _SPEC_ID_RE.match(replacement) or replacement == spec_id:
        raise RetireError(
            f"replacement {replacement!r} is not another requirement ID"
        )
    if replacement not in load_registry(root / "specs").all_specs:
        raise RetireError(
            f"replacement {replacement} is not declared in specs/"
        )


def retire_spec(
    spec_id: str,
    *,
    why: str,
    retired_by: str,
    replacement: str | None = None,
    repo_root: Path | None = None,
    today: datetime.date | None = None,
    record_history: bool = True,
    base_ref: str | None = None,
) -> list[tuple[str, int, str]]:
    """Move *spec_id* from its spec file to the archive (MS-09-001/002/005).

    The working-tree block is removed; the block at the merge base of
    *base_ref* and ``HEAD`` is archived (:func:`published_text`, MS-09-008).

    Returns the cross-references still to repoint (MS-09-003).

    Raises:
        RetireError: The ID is malformed, already archived, undeclared in the
            working tree or at the base, the base cannot be resolved, or the
            remaining spec files no longer load once it is removed.
            Nothing is changed in that case.
    """
    root = _repo_root(repo_root)
    spec_dir = root / "specs"
    _validate_request(root, spec_id, why, replacement)

    path, lines, block = _locate(spec_dir, spec_id)
    published = published_text(root, spec_id, base_ref)
    if published.text != "\n".join(block.slice(lines)):
        logger.warning(
            "%s was edited since the merge base %s; the archive keeps the "
            "published text and the edit is dropped",
            spec_id,
            published.base[:12],
        )
    original = path.read_text(encoding="utf-8")
    remaining = lines[: block.start] + lines[block.end :]
    today = today or datetime.datetime.now(datetime.UTC).date()
    entry = render_archive_entry(
        spec_id,
        retired_on=today,
        retired_by=retired_by,
        why=why,
        replacement=replacement,
        last_text=published.text,
    )

    archive = retired_specs_dir(root)
    archive_file = archive / f"{spec_id}.md"
    archive_existed = archive.exists()
    path.write_text("\n".join(remaining) + "\n", encoding="utf-8")
    try:
        try:
            load_registry(spec_dir)
        except (ValidationError, ValueError) as exc:
            raise RetireError(
                f"removing {spec_id} leaves {path.name} unloadable "
                f"(is it the last item in its group?):\n{exc}"
            ) from exc
        archive.mkdir(parents=True, exist_ok=True)
        archive_file.write_text(entry, encoding="utf-8")
        if record_history:
            _record_history(
                root, spec_id, path, why, retired_by, replacement, today
            )
    except BaseException:
        # Whole retirement, or none (MS-09-012): undo the spec edit and the
        # archive entry on any failure.
        path.write_text(original, encoding="utf-8")
        archive_file.unlink(missing_ok=True)
        if (
            not archive_existed
            and archive.is_dir()
            and not any(archive.iterdir())
        ):
            archive.rmdir()
        raise
    return find_cross_references(root, spec_id)


def _record_history(
    root: Path,
    spec_id: str,
    spec_path: Path,
    why: str,
    retired_by: str,
    replacement: str | None,
    today: datetime.date,
) -> None:
    """Write the MS-09-002 implementation-history entry for the removal."""
    body = (
        f"Retired {spec_id} from `{spec_path.relative_to(root)}` "
        f"({retired_by}).\n\nWhy: {why.strip()}\n"
    )
    if replacement:
        body += f"\nReplacement: {replacement}\n"
    body += f"\nFinal text: `{RETIRED_SPECS_RELPATH}/{spec_id}.md`.\n"
    content = _build_content(
        HistoryEntryType.implementation,
        f"Retired requirement {spec_id}",
        f"SPEC-RETIRE-{spec_id}",
        body,
    )
    append_history_entry(
        HistoryEntryType.implementation,
        content,
        repo_root=root,
        target_date=today,
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: ``uv run spec-retire <ID> --why ... --by ...``."""
    parser = argparse.ArgumentParser(
        prog="spec-retire",
        description=(
            "Move a requirement from specs/ to plan/retired-specs/, record "
            "the removal in plan/history/, and list the citations to repoint."
        ),
    )
    parser.add_argument("spec_id", help="ID of the requirement to retire")
    parser.add_argument(
        "--why", required=True, help="why the requirement is being removed"
    )
    parser.add_argument(
        "--by",
        required=True,
        dest="retired_by",
        help="the issue or PR retiring it, e.g. '#3918'",
    )
    parser.add_argument(
        "--replacement",
        help="ID of the requirement that replaces it, if any",
    )
    parser.add_argument(
        "--base",
        dest="base_ref",
        help=(
            "branch whose text is archived, read at its merge base with "
            "HEAD (default: origin/$GITHUB_BASE_REF, else origin/main)"
        ),
    )
    args = parser.parse_args(argv)
    try:
        refs = retire_spec(
            args.spec_id,
            why=args.why,
            retired_by=args.retired_by,
            replacement=args.replacement,
            base_ref=args.base_ref,
        )
    except RetireError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(
        f"Retired {args.spec_id} -> {RETIRED_SPECS_RELPATH}/{args.spec_id}.md"
    )
    if refs:
        target = args.replacement or "its replacement"
        print(
            f"Repoint these {len(refs)} citation(s) to {target} (MS-09-003):"
        )
        for rel, n, line in refs:
            print(f"  {rel}:{n}: {line[:100]}")
    else:
        print("No remaining citations to repoint.")


if __name__ == "__main__":
    main()
