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
"""The one record of the CSAF 2.1 draft revision this codebase follows (CSAF-05-001).

Every CSAF 2.1 draft uses the same ``$schema`` value, so a document cannot say
which draft it follows. ``pin.json`` names the revision once, and the pinned
local copy, the generated models and the crosswalk pages all read it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from vultron.primitives import NonEmptyString

#: This package's directory.
CSAF_PACKAGE_DIR = Path(__file__).resolve().parent
#: The pin record.
PIN_PATH = CSAF_PACKAGE_DIR / "pin.json"
#: The pinned local copy of the schemas, laid out as their paths in ``sources``.
PINNED_COPY_DIR = CSAF_PACKAGE_DIR / "schemas"
#: The package the models generated from the pinned local copy live in.
MODELS_DIR = CSAF_PACKAGE_DIR / "models"


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


class CsafPin(BaseModel):
    """One revision of the CSAF 2.1 draft, and where its schemas sit locally."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repository: NonEmptyString = Field(
        description="The repository of the CSAF Technical Committee."
    )
    commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")] = Field(
        description="The full commit hash the pinned local copy was taken from."
    )
    draft_stage: NonEmptyString = Field(
        description="The draft stage of that commit, such as ``CSD04``."
    )
    root: RelativePath = Field(
        description="The path of the CSAF schema inside the pinned local copy."
    )
    sources: dict[NonEmptyString, RelativePath] = Field(
        min_length=1,
        description=(
            "Each referenced schema's URL, mapped to its path inside the "
            "pinned local copy."
        ),
    )

    sha256: dict[RelativePath, Sha256] = Field(
        description=(
            "The SHA-256 digest of each file of the pinned local copy, so a "
            "hand edit to the copy is detected."
        ),
    )

    @model_validator(mode="after")
    def _files_agree(self) -> CsafPin:
        files = set(self.sources.values())
        if self.root not in files:
            raise ValueError(f"root {self.root!r} is not a file in sources")
        if set(self.sha256) != files:
            raise ValueError("sha256 must list exactly the files in sources")
        return self

    @property
    def short_commit(self) -> str:
        """Return the seven-character commit abbreviation the docs cite."""
        return self.commit[:7]


def file_sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of the file at *path*."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pin(path: Path = PIN_PATH) -> CsafPin:
    """Read and validate the pin record at *path*."""
    return CsafPin.model_validate_json(path.read_bytes())


__all__ = [
    "CSAF_PACKAGE_DIR",
    "MODELS_DIR",
    "PINNED_COPY_DIR",
    "PIN_PATH",
    "CsafPin",
    "RelativePath",
    "Sha256",
    "file_sha256",
    "load_pin",
]
