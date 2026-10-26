"""File I/O shared by the baselines of the ``docs/`` checks.

A baseline is a text file under an explanatory ``#`` header, one entry per
line. Each check owns what an entry means and which way the list may move: the
``docs-level-order`` baseline lists ``page | term | reason`` and the
``docs-thread-order`` baseline ``thread | page | term | reason``, both
shrink-only; the ``docs-legacy-urls`` baseline lists published page paths and
only grows. This module owns the file shape, the ``|``-separated keyed entry,
and what a shrink-only check does with one, so every check reads, applies and
prunes its baseline the same way. The ``docs-frontmatter`` baseline, which
listed page paths, reached zero and was retired (#3528).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, cast

from vultron.metadata.file_loading import FailureCollector, MetadataLoadError

#: The key of a keyed entry: every field but its trailing reason.
EntryKey = tuple[str, ...]


class BaselineEntry(NamedTuple):
    """One tolerated violation: why it is unfixed, and where it is listed."""

    reason: str
    line: int


def entry_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Yield ``(line number, line)`` for every entry in the baseline at *path*.

    Blank lines and lines starting with ``#`` are skipped. A missing file has
    no entries.
    """
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
        if line.strip() and not line.lstrip().startswith("#"):
            yield number, line


def write_entries(path: Path, header: str, entries: Iterable[str]) -> None:
    """Write *entries* sorted, one per line, under *header*."""
    body = "".join(f"{entry}\n" for entry in sorted(entries))
    path.write_text(header + "\n" + body, encoding="utf-8")


def read_keyed_entries(
    path: Path, key_fields: tuple[str, ...]
) -> dict[EntryKey, BaselineEntry]:
    """Return ``{key: entry}`` for every ``<key fields> | reason`` entry.

    Args:
        key_fields: The names of the key's fields, in order, for the message
            naming a malformed entry.

    Raises:
        MetadataLoadErrors: Naming ``path:line`` for every entry that is not
            the key fields and a reason, each non-empty, or that repeats an
            earlier entry's key.
    """
    shape = " | ".join((*key_fields, "reason"))
    entries: dict[EntryKey, BaselineEntry] = {}
    collector = FailureCollector()
    for number, line in entry_lines(path):
        with collector.attempt():
            fields = [f.strip() for f in line.split("|")]
            if len(fields) != len(key_fields) + 1 or not all(fields):
                raise MetadataLoadError(
                    f"an entry is `{shape}`, each non-empty; every baselined "
                    "violation names why it is unfixed",
                    path=path.name,
                    line=number,
                )
            *key, reason = fields
            if tuple(key) in entries:
                raise MetadataLoadError(
                    f"repeats the entry for {' | '.join(key)}",
                    path=path.name,
                    line=number,
                )
            entries[tuple(key)] = BaselineEntry(reason, number)
    collector.raise_if_any(
        summary=f"{len(collector.failures)} malformed baseline entry(ies):"
    )
    return entries


def write_keyed_entries[K: EntryKey](
    path: Path, header: str, entries: Mapping[K, str]
) -> None:
    """Write ``{key: reason}`` *entries* sorted, under *header*."""
    write_entries(
        path,
        header,
        (" | ".join((*key, reason)) for key, reason in entries.items()),
    )


def apply_baseline[K: EntryKey](
    found: Mapping[K, MetadataLoadError],
    allowed: Mapping[K, object],
    *,
    stale: Callable[[K], MetadataLoadError],
) -> tuple[list[K], list[MetadataLoadError]]:
    """Split *found* violations by a shrink-only baseline.

    Args:
        found: Each violation's key, mapped to the finding it raises when
            the baseline does not list it.
        allowed: The baselined keys.
        stale: The finding for a baselined key that is no longer a
            violation, so the list can only shrink.

    Returns:
        The baselined keys found, sorted, and every finding: each unlisted
        violation, then each stale entry.
    """
    baselined = sorted(key for key in found if key in allowed)
    faults = [error for key, error in found.items() if key not in allowed]
    faults += [stale(key) for key in sorted(set(allowed) - set(found))]
    return baselined, faults


def prune_entries[K: EntryKey](
    current: Mapping[K, str],
    found: Iterable[K],
    unread: Iterable[str],
    page_of: Callable[[K], str],
) -> dict[K, str]:
    """The entries of *current* a prune keeps.

    An entry stays while its violation is still found, or while its page is
    one the check could not read: that page's violation is unknown, not
    fixed. A prune never adds an entry, so it cannot grow the baseline.

    Args:
        unread: The ``docs/``-prefixed paths of pages that failed to load.
        page_of: The ``docs/``-relative page an entry's key names.
    """
    found_keys = set(found)
    unread_paths = set(unread)
    return {
        key: reason
        for key, reason in current.items()
        if key in found_keys or f"docs/{page_of(key)}" in unread_paths
    }


@dataclass(frozen=True, slots=True)
class KeyedBaseline[K: EntryKey]:
    """A shrink-only baseline file of ``<key fields> | reason`` entries.

    Attributes:
        path: The committed baseline.
        header: The explanatory header written above the entries.
        key_fields: The names of the key's fields, in order.
    """

    path: Path
    header: str
    key_fields: tuple[str, ...]

    def entries(self, path: Path | None = None) -> dict[K, BaselineEntry]:
        """Return ``{key: entry}`` for every baselined violation.

        Raises:
            MetadataLoadErrors: As :func:`read_keyed_entries`.
        """
        read = read_keyed_entries(path or self.path, self.key_fields)
        # read_keyed_entries refuses an entry whose key does not have exactly
        # len(key_fields) fields, so every key it returns is a K.
        return cast("dict[K, BaselineEntry]", read)

    def read(self, path: Path | None = None) -> dict[K, str]:
        """Return ``{key: reason}`` for every baselined violation.

        Raises:
            MetadataLoadErrors: As :func:`read_keyed_entries`.
        """
        return {key: entry.reason for key, entry in self.entries(path).items()}

    def write(
        self, entries: Mapping[K, str], path: Path | None = None
    ) -> None:
        """Write *entries* sorted, under the explanatory header."""
        write_keyed_entries(path or self.path, self.header, entries)

    def check(
        self,
        found: Mapping[K, MetadataLoadError],
        override: Mapping[K, str] | None,
        *,
        stale_detail: Callable[[K], str],
        path: Path | None = None,
    ) -> tuple[list[K], list[MetadataLoadError]]:
        """Split *found* by the baseline at *path*, or by *override*.

        A stale entry is located at its line in the file; an *override* (a
        test's in-memory baseline) has no lines to name. *path* defaults to
        :attr:`path`; a check passes its module's ``BASELINE_PATH`` so a test
        can redirect it.

        Returns:
            As :func:`apply_baseline`.
        """
        path = path or self.path
        entries = self.entries(path) if override is None else {}
        allowed: Mapping[K, object] = entries if override is None else override

        def stale(key: K) -> MetadataLoadError:
            entry = entries.get(key)
            return MetadataLoadError(
                stale_detail(key),
                path=path.name,
                line=entry.line if entry else None,
            )

        return apply_baseline(found, allowed, stale=stale)

    def prune(
        self,
        found: Iterable[K],
        unread: Iterable[str],
        page_of: Callable[[K], str],
        path: Path | None = None,
    ) -> int:
        """Rewrite the baseline at *path* with the entries a prune keeps.

        Never adds an entry; see :func:`prune_entries` for *unread* and
        *page_of*.

        Returns:
            How many entries were removed.
        """
        path = path or self.path
        current = self.read(path)
        keep = prune_entries(current, found, unread, page_of)
        self.write(keep, path)
        return len(current) - len(keep)
