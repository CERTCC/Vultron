#!/usr/bin/env python

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

"""The ids the VINCE translation mints, and how it cites a VINCE record.

Every id is a ``urn:uuid`` (version 5) value minted from the VINCE instance
and the case, so the same records always give the same ids.  An id holds no
VINCE name or contact in clear text; it is a hash a reader could only match
against a name it already holds.  The Reporter's id is minted from the case
alone, whether or not it shared a contact, so no contact detail goes into
the hash (VSD-01-003); a shared contact is named on its participant record
instead (VINCE-PA-03).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from vultron.adapters.connectors.vince.records import VinceCase


def vince_case_url(comm_url: str, case: VinceCase) -> str:
    """The VINCE web address of *case*, under the VINCE Comm root *comm_url*.

    VINCE Comm serves a case's page at ``case/<pk>/`` (VINCE-CA-02).
    """
    return f"{comm_url.rstrip('/')}/case/{case.pk}/"


def _urn(namespace: UUID, name: str) -> str:
    return f"urn:uuid:{uuid5(namespace, name)}"


@dataclass(frozen=True)
class CaseIds:
    """Every id the translation of one case mints, and its citations."""

    comm_url: str
    case: VinceCase

    @property
    def _instance(self) -> UUID:
        return uuid5(NAMESPACE_URL, self.comm_url.rstrip("/"))

    @property
    def case_url(self) -> str:
        return vince_case_url(self.comm_url, self.case)

    @property
    def _case(self) -> UUID:
        return uuid5(NAMESPACE_URL, self.case_url)

    @property
    def case_id(self) -> str:
        return _urn(self._case, "case")

    @property
    def coordinator(self) -> str:
        """CERT/CC, the same on every case of the instance."""
        return _urn(self._instance, "coordinator")

    def vendor(self, name: str) -> str:
        """The vendor VINCE names *name*, the same on every case."""
        return _urn(self._instance, f"vendor:{name}")

    def reporter(self, *, shared: bool) -> str:
        """The case's Reporter: one with a shared contact (VINCE-PA-03) or
        the withheld placeholder (VINCE-PA-04)."""
        return _urn(self._case, "reporter" if shared else "reporter:withheld")

    def minted(self, label: str) -> str:
        """The id of the case's object *label* names."""
        return _urn(self._case, label)

    def participant(self, actor: str) -> str:
        """The id of *actor*'s participant record on the case."""
        return self.minted(f"participant:{actor}")

    def record(self, read: str, index: int | None = None) -> str:
        """The VINCE record *read*, an item of it when *index* is set:
        ``case/<vuid>/<read>/[<index>]``."""
        path = "" if read == "case" else f"{read}/"
        where = f"case/{self.case.vuid}/{path}"
        return where if index is None else f"{where}[{index}]"


__all__ = ["CaseIds", "vince_case_url"]
