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
which draft it follows. ``third_party/csaf/pin.json`` names the revision once,
and the pinned local copy, the generated models and the crosswalk pages all
read it. The copy and the record are third-party files outside ``vultron/``;
only the regeneration script, the corpus script and the tests read them, never
the runtime.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field, model_validator

from vultron.metadata.pin_record import (
    PinRecord,
    RelativePath,
    Sha256,
    file_sha256,
)
from vultron.primitives import NonEmptyString

#   parents[0] = csaf, [1] = metadata, [2] = vultron, [3] = <repo root>
_REPO_ROOT = Path(__file__).resolve().parents[3]
#: Where the pinned local copy and its pin record sit: outside ``vultron/``,
#: which holds only this project's own code.
THIRD_PARTY_CSAF_DIR = _REPO_ROOT / "third_party" / "csaf"
#: The pin record.
PIN_PATH = THIRD_PARTY_CSAF_DIR / "pin.json"
#: The pinned local copy of the schemas, laid out as their paths in ``sources``.
PINNED_COPY_DIR = THIRD_PARTY_CSAF_DIR / "schemas"
#: The names of the licence files kept beside each source's files in the copy.
#: They are not schemas, so the pin record does not list them.
LICENCE_FILE_NAMES = frozenset({"LICENSE", "NOTICE"})
#: The package the models generated from the pinned local copy live in.
MODELS_DIR = _REPO_ROOT / "vultron" / "wire" / "csaf" / "models"


class CsafPin(PinRecord):
    """One revision of the CSAF 2.1 draft, and where its schemas sit locally."""

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

    @model_validator(mode="after")
    def _root_is_a_source(self) -> CsafPin:
        if self.root not in set(self.sources.values()):
            raise ValueError(f"root {self.root!r} is not a file in sources")
        return self

    @property
    def short_commit(self) -> str:
        """Return the seven-character commit abbreviation the docs cite."""
        return self.commit[:7]


def load_pin(path: Path = PIN_PATH) -> CsafPin:
    """Read and validate the pin record at *path*."""
    return CsafPin.model_validate_json(path.read_bytes())


__all__ = [
    "LICENCE_FILE_NAMES",
    "MODELS_DIR",
    "PINNED_COPY_DIR",
    "PIN_PATH",
    "THIRD_PARTY_CSAF_DIR",
    "CsafPin",
    "RelativePath",
    "Sha256",
    "file_sha256",
    "load_pin",
]
