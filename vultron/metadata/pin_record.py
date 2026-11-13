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
"""The shape every pin record under ``third_party/`` shares.

A pin record maps each source URL to a file of a pinned local copy and records
each file's SHA-256 digest, so a hand edit to the copy is detected. The CSAF
schemas (CSAF-05-002) and the JSON-LD contexts (VM-10-011) both use it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from vultron.primitives import NonEmptyString


def _relative_posix_path(value: str) -> str:
    """Return *value* when it is a plain relative POSIX path, else raise.

    Every segment must be a real name: no empty, ``.`` or ``..`` segment and no
    backslash, so the path stays inside the pinned local copy on any platform.
    """
    parts = value.split("/")
    if "\\" in value or any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"{value!r} is not a relative path inside the copy")
    return value


RelativePath = Annotated[NonEmptyString, AfterValidator(_relative_posix_path)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class PinRecord(BaseModel):
    """Each source's URL, its file in the pinned local copy, and its digest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sources: dict[NonEmptyString, RelativePath] = Field(
        min_length=1,
        description=(
            "Each source's URL, mapped to its path inside the pinned local copy."
        ),
    )

    sha256: dict[RelativePath, Sha256] = Field(
        description=(
            "The SHA-256 digest of each file of the pinned local copy, so a "
            "hand edit to the copy is detected."
        ),
    )

    @model_validator(mode="after")
    def _digests_cover_the_sources(self) -> Self:
        if set(self.sha256) != set(self.sources.values()):
            raise ValueError("sha256 must list exactly the files in sources")
        return self


def file_sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of the file at *path*."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = ["PinRecord", "RelativePath", "Sha256", "file_sha256"]
