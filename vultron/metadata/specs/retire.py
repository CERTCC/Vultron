"""Retired-requirement archive and the ``spec-retire`` helper.

A requirement is removed from ``specs/`` rather than marked deprecated
(MS-09-001).
Its final text is kept, one file per ID, in ``plan/retired-specs/`` (MS-09-005)
so a citation of the ID still resolves to something, while the retired text
stays out of every spec loader and out of agent context.
An ID in the archive is never reused (MS-09-004).

Usage::

    uv run spec-retire <ID> --why "..." --by "#N" --replacement <NEW-ID>

The helper moves the item's text from its spec file to the archive, records the
removal in the implementation history (MS-09-002), and lists every remaining
cross-reference that MS-09-003 requires repointing.
"""

from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from vultron.metadata.base import repo_root as _repo_root
from vultron.metadata.history.cli import _build_content, append_history_entry
from vultron.metadata.history.types import HistoryEntryType
from vultron.metadata.specs.registry import load_registry

#: Archive location relative to the repository root (MS-09-005).
RETIRED_SPECS_RELPATH = Path("plan") / "retired-specs"

_README = "README.md"
_SPEC_ID_RE = re.compile(r"^[A-Z]{2,8}-\d{2}-\d{3}$")

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


def _locate(spec_dir: Path, spec_id: str) -> tuple[Path, list[str], _Block]:
    for path in sorted(spec_dir.glob("*.yaml")):
        lines = path.read_text(encoding="utf-8").splitlines()
        block = _find_block(lines, spec_id)
        if block is not None:
            return path, lines, block
    raise RetireError(f"{spec_id} is not declared in any {spec_dir}/*.yaml")


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
    pattern = re.compile(rf"(?<![A-Za-z0-9-]){re.escape(spec_id)}(?!\d)")
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
) -> list[tuple[str, int, str]]:
    """Move *spec_id* from its spec file to the archive (MS-09-001/002/005).

    Returns the cross-references still to repoint (MS-09-003).

    Raises:
        RetireError: The ID is malformed, already archived, undeclared, or the
            remaining spec files no longer load once it is removed.
            Nothing is changed in that case.
    """
    root = _repo_root(repo_root)
    spec_dir = root / "specs"
    _validate_request(root, spec_id, why, replacement)

    path, lines, block = _locate(spec_dir, spec_id)
    original = path.read_text(encoding="utf-8")
    remaining = lines[: block.start] + lines[block.end :]
    today = today or datetime.datetime.now(datetime.UTC).date()
    entry = render_archive_entry(
        spec_id,
        retired_on=today,
        retired_by=retired_by,
        why=why,
        replacement=replacement,
        last_text="\n".join(block.slice(lines)),
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
        # Whole retirement, or none (MS-09-006): undo the spec edit and the
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
    args = parser.parse_args(argv)
    try:
        refs = retire_spec(
            args.spec_id,
            why=args.why,
            retired_by=args.retired_by,
            replacement=args.replacement,
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
