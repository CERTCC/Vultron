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
"""The committed cleared-case list (ADR-0189 rule 3, VSD-02-002, VSD-02-003).

A recorded VINCE response with no synthetic marker may be committed only when
a maintainer has cleared its VINCE case id. Each entry names one case id and
links the maintainer's clearance comment::

    cleared:
      - case_id: "123456"
        clearance: https://github.com/CERTCC/Vultron/issues/1#issuecomment-2

A Coding Agent may ask a maintainer to clear a case id, and never adds an
entry (VSD-02-004): no check can tell an agent's comment from a maintainer's,
so review holds that rule.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from vultron.metadata.file_loading import load_yaml, validate

#: A VINCE case id: the digits of a ``vuid``, as the API's ``case/<vuid>/``
#: path and a case's ``vuid`` field carry it.
CASE_ID = re.compile(r"\d+")

#: A comment on an issue or pull request of this repository.
CLEARANCE_LINK = re.compile(
    r"https://github\.com/CERTCC/Vultron/(?:issues|pull)/\d+"
    r"#issuecomment-\d+"
)


class ClearedCase(BaseModel):
    """One maintainer clearance: one case id and the comment that cleared it.

    A plain model: it is repository tooling, never protocol data.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    clearance: str

    @field_validator("case_id", mode="before")
    @classmethod
    def _one_case_id(cls, value: object) -> object:
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str) or not CASE_ID.fullmatch(value):
            raise ValueError(
                "must be exactly one VINCE case id, the digits of its vuid "
                f"(a clearance covers one case, VSD-02-002), not {value!r}"
            )
        return value

    @field_validator("clearance")
    @classmethod
    def _links_a_comment(cls, value: str) -> str:
        if not CLEARANCE_LINK.fullmatch(value):
            raise ValueError(
                "must link the maintainer's clearance comment, "
                "https://github.com/CERTCC/Vultron/issues/<n>#issuecomment-<m>"
                f" (VSD-02-002), not {value!r}"
            )
        return value


class ClearedCaseList(BaseModel):
    """The whole cleared-case list. A plain model, as :class:`ClearedCase`."""

    model_config = ConfigDict(extra="forbid")

    cleared: list[ClearedCase]

    @model_validator(mode="after")
    def _each_case_once(self) -> ClearedCaseList:
        ids = [entry.case_id for entry in self.cleared]
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        if repeated:
            raise ValueError(
                f"case ids listed more than once: {', '.join(repeated)}"
            )
        return self

    def case_ids(self) -> frozenset[str]:
        """Every cleared case id."""
        return frozenset(entry.case_id for entry in self.cleared)


def load_cleared_cases(path: Path, root: Path) -> ClearedCaseList:
    """Read and validate the cleared-case list at *path*.

    Raises:
        MetadataLoadError: When the file does not parse, or an entry lacks a
            case id or a clearance link, names more than one case id, or
            repeats a case id (VSD-02-003).
        FileNotFoundError: When the list is missing.
    """
    data = load_yaml(path, root=root)
    return validate(
        ClearedCaseList,
        data,
        path=path,
        root=root,
        prefix="cleared-case list refused (VSD-02-003)",
    )


__all__ = [
    "CASE_ID",
    "CLEARANCE_LINK",
    "ClearedCase",
    "ClearedCaseList",
    "load_cleared_cases",
]
