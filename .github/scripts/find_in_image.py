#!/usr/bin/env python3
"""Search a saved Docker image for a marker string, in every layer.

``docker image save`` writes an image as a tar archive: one tar archive per
layer (plain or compressed), plus the image config and manifests as JSON.  This
script reads every member of that archive.  It searches the raw bytes of each
member, which covers the config (where an ``ENV`` or a build argument's value
would land) and the manifests.  For each member that is itself a tar archive (a
layer), it also searches the path, the link target and the contents of every
file in that layer.  A file that a later layer deletes is still in the earlier
layer, so it is still found.

The marker is read from the environment variable that ``--marker-env`` names,
so the value never appears on a command line.  The case shadow tool's CI job
builds the image with a marker credential in the build environment and runs
this script to prove that no layer holds it (SHD-02-003).

Exit status: 0 when the image has at least one layer and the marker is in none
of them; 1 when the marker is found, with every place named on stdout; 2 when
the search cannot run (no marker, no layer, or a layer this script cannot
read), so a search that checked nothing never passes.

Usage: find_in_image.py --marker-env NAME IMAGE_TAR
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tarfile
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import IO

#: Bytes read from a file at a time while it is searched.
CHUNK_SIZE = 1 << 20

#: Leading bytes of the compressed formats a layer can use.  A member that
#: starts with one of these is a layer, so a failure to read it as a tar
#: archive is an error, not a sign that it is metadata.
_COMPRESSED_MAGIC = (
    b"\x1f\x8b",  # gzip
    b"BZh",  # bzip2
    b"\xfd7zXZ\x00",  # xz
    b"\x28\xb5\x2f\xfd",  # zstd
)

#: Offset and value of the ``ustar`` magic in an uncompressed tar header.
_USTAR_OFFSET = 257
_USTAR_MAGIC = b"ustar"


class SearchError(Exception):
    """The search cannot run, so its result would mean nothing."""


def contains(
    stream: IO[bytes], needle: bytes, chunk_size: int = CHUNK_SIZE
) -> bool:
    """Whether *stream* holds *needle*, read in chunks of *chunk_size* bytes.

    Each chunk is searched together with the last ``len(needle) - 1`` bytes of
    the one before it, so a marker split across two chunks is still found.
    """
    keep = len(needle) - 1
    tail = b""
    while chunk := stream.read(chunk_size):
        window = tail + chunk
        if needle in window:
            return True
        tail = window[-keep:] if keep else b""
    return False


def _looks_like_archive(path: Path) -> bool:
    with path.open("rb") as handle:
        head = handle.read(_USTAR_OFFSET + len(_USTAR_MAGIC))
    if head.startswith(_COMPRESSED_MAGIC):
        return True
    return head[_USTAR_OFFSET:] == _USTAR_MAGIC


def _open_archive(path: Path, failure: str) -> tarfile.TarFile:
    """The tar archive at *path*, plain or compressed.

    Raises :class:`SearchError`, starting with *failure*, when it cannot be read.
    """
    try:
        return tarfile.open(path, mode="r:*")
    except (tarfile.TarError, OSError) as err:
        raise SearchError(f"{failure}: {err}") from err


def _layer_hits(path: Path, label: str, needle: bytes) -> Iterator[str]:
    """Every place in the layer archive at *path* that holds *needle*."""
    with _open_archive(path, f"{label}: cannot read this layer") as layer:
        for member in layer:
            where = f"{label}:{member.name}"
            if (
                needle in member.name.encode()
                or needle in member.linkname.encode()
            ):
                yield f"{where} (in its path or link target)"
            if not member.isfile():
                continue
            extracted = layer.extractfile(member)
            if extracted is not None and contains(extracted, needle):
                yield where


def search(image_tar: Path, needle: bytes) -> tuple[int, list[str]]:
    """Search the saved image *image_tar* for *needle*.

    Returns the number of layers searched and every place the needle is in.
    Raises :class:`SearchError` when the needle is empty, the image cannot be
    read, or the image holds no layer.
    """
    if not needle:
        raise SearchError("the marker is empty, so every search would pass")
    hits: list[str] = []
    layers = 0
    with (
        _open_archive(
            image_tar, f"{image_tar}: cannot read the image"
        ) as image,
        tempfile.TemporaryDirectory() as scratch,
    ):
        member_copy = Path(scratch) / "member"
        for member in image:
            if needle in member.name.encode():
                hits.append(f"{member.name} (in its path)")
            if not member.isfile():
                continue
            extracted = image.extractfile(member)
            if extracted is None:
                continue
            with member_copy.open("wb") as out:
                shutil.copyfileobj(extracted, out)
            with member_copy.open("rb") as raw:
                if contains(raw, needle):
                    hits.append(member.name)
            if _looks_like_archive(member_copy):
                layers += 1
                hits.extend(_layer_hits(member_copy, member.name, needle))
    if layers == 0:
        raise SearchError(
            f"{image_tar}: holds no layer, so nothing was searched"
        )
    return layers, hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Search a saved Docker image for a marker, in every layer."
    )
    parser.add_argument(
        "--marker-env",
        required=True,
        help="The environment variable that holds the marker.",
    )
    parser.add_argument(
        "image_tar", type=Path, help="The `docker image save` output."
    )
    args = parser.parse_args(argv)
    marker = os.environ.get(args.marker_env, "")
    if not marker:
        print(
            f"::error::Cannot search the image: {args.marker_env} is unset or empty"
        )
        return 2
    try:
        layers, hits = search(args.image_tar, marker.encode())
    except SearchError as err:
        print(f"::error::Cannot search the image: {err}")
        return 2
    if hits:
        for hit in hits:
            print(f"::error::The marker from {args.marker_env} is in {hit}")
        return 1
    print(
        f"Searched {layers} layer(s) and the image metadata: "
        f"the marker from {args.marker_env} is in none of them."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
