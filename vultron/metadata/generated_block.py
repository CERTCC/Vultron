"""Splice generated markdown between a marker pair in hand-written prose.

Several committed artifacts are part generated, part hand-written: a README
whose scenario table is generated (DEMOCI-11-005), a section landing page whose
contents listing is generated (DF-11-005). Each keeps its prose and replaces
only what sits between an opening and a closing marker, so the locating logic
lives here once (CS-22-001).
"""

from __future__ import annotations


def splice_between(
    current: str, body: str, path: str, begin: str, end: str
) -> str:
    """Return *current* with the text between *begin* and *end* replaced.

    Args:
        current: Current file contents.
        body: Generated markdown to place between the markers.
        path: Repository-relative path, for error attribution.
        begin: The opening marker, matched literally.
        end: The closing marker, matched literally.

    Raises:
        ValueError: If a marker is missing or duplicated, or the pair is
            inverted. Appending the block when the markers are absent would
            leave the stale hand-written copy in place above it, so this fails
            instead.
    """
    for marker, label in ((begin, "begin"), (end, "end")):
        count = current.count(marker)
        if count != 1:
            raise ValueError(
                f"{path}: found {count} generated-block {label} markers, "
                f"expected exactly 1. The marker text is:\n  {marker}"
            )
    start = current.index(begin)
    stop = current.index(end)
    if stop < start:
        raise ValueError(
            f"{path}: the generated-block end marker precedes the begin marker"
        )
    head = current[: start + len(begin)]
    tail = current[stop:]
    return f"{head}\n\n{body}\n\n{tail}"
