"""Read ADR and spec texts from git: the base, blobs at a revision and the edited ADRs."""

from __future__ import annotations

import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path

#: Files under docs/adr/ that are not decision records.
_NON_ADR_FILES = {"index.md", "README.md"}


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False
    )


def verify_base(base: str) -> None:
    """Raise ``ValueError`` unless ``base`` names a commit.

    Without this, a mistyped ref reads as "every ADR is new" and the gate
    passes everything.
    """
    res = _git("rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    if res.returncode != 0:
        raise ValueError(f"--base {base!r} is not a commit in this repository")


def _text_at(base: str, path: Path) -> str | None:
    """Return the text of ``path`` at ``base``, or None if absent there."""
    res = _git("show", f"{base}:{path.as_posix()}")
    return res.stdout if res.returncode == 0 else None


def _texts_at(ref: str, paths: Sequence[str]) -> dict[str, str]:
    """Return the text of each of ``paths`` at ``ref``, keyed in order.

    One ``git cat-file --batch`` reads every path, where :func:`_text_at`
    spawns a process per file. A path that is not a file at ``ref`` reads as
    empty, as :func:`_text_at`'s ``None`` does to its callers.
    """
    texts = dict.fromkeys(paths, "")
    res = subprocess.run(
        ["git", "cat-file", "--batch"],
        input="".join(f"{ref}:{path}\n" for path in paths).encode(),
        capture_output=True,
        check=False,
    )
    if res.returncode != 0:
        return texts
    out, pos = res.stdout, 0
    for path in paths:
        eol = out.index(b"\n", pos)
        # "<oid> <type> <size>" then the content, or "<name> missing".
        header = out[pos:eol]
        pos = eol + 1
        if header.endswith((b" missing", b" ambiguous")):
            continue
        _, kind, size = header.split()
        if kind == b"blob":
            texts[path] = out[pos : pos + int(size)].decode("utf-8")
        pos += int(size) + 1
    return texts


def _rename_sources(base: str) -> dict[Path, Path]:
    """Map each renamed path to the path it had at ``base``."""
    res = _git("diff", "-M", "--name-status", "--diff-filter=R", base)
    out: dict[Path, Path] = {}
    for line in res.stdout.splitlines():
        _, old, new = line.split("\t")
        out[Path(new)] = Path(old)
    return out


def edited_adrs(
    paths: Iterable[Path], base: str
) -> list[tuple[Path, str | None, str]]:
    """Pair each edited ADR's text at ``base`` with its working-tree text.

    Returns ``(path, old_text, new_text)`` for every path that is a decision
    record present in the working tree; ``index.md``, ``README.md``, files
    starting with ``_`` and deleted paths are skipped. A renamed path is
    paired with the text of the path it had at ``base``, and a path with no
    text at ``base`` (a new ADR) gets ``None``. Raises ``ValueError`` if
    ``base`` is not a commit.

    Shared by every check that judges an edit rather than the corpus, so each
    one reads the merge base the same way.
    """
    verify_base(base)
    renames = _rename_sources(base)
    out: list[tuple[Path, str | None, str]] = []
    for path in paths:
        if path.name in _NON_ADR_FILES or path.name.startswith("_"):
            continue
        if not path.is_file():
            continue
        old_text = _text_at(base, renames.get(path, path))
        out.append((path, old_text, path.read_text(encoding="utf-8")))
    return out
