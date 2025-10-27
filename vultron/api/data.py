#!/usr/bin/env python
"""
Basic Data Module for Vultron API
"""
#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from typing import TypeVar, TypeAlias

from pydantic import BaseModel, Field

from vultron.as_vocab.base.objects.activities.transitive import (
    as_Offer,
    as_Invite,
)
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport

StorableThing: TypeAlias = TypeVar(
    "StorableThing",
    as_Offer,
    as_Invite,
    VulnerabilityReport,
    VulnerabilityCase,
)


class _Things(BaseModel):
    offers: list[as_Offer] = Field(default_factory=list)
    invites: list[as_Invite] = Field(default_factory=list)
    reports: list[VulnerabilityReport] = Field(default_factory=list)
    cases: list[VulnerabilityCase] = Field(default_factory=list)

    def _do(self, thing: StorableThing, action: str):
        match thing.as_type:
            case "Offer":
                getattr(self.offers, action)(thing)  # type: ignore
            case "Invite":
                getattr(self.invites, action)(thing)  # type: ignore
            case "VulnerabilityReport":
                getattr(self.reports, action)(thing)  # type: ignore
            case "VulnerabilityCase":
                getattr(self.cases, action)(thing)  # type: ignore
            case _:
                raise ValueError(f"Unknown thing type: {thing.as_type}")

    def append(self, thing: StorableThing):
        self._do(thing, "append")

    def clear(self):
        self.offers.clear()
        self.invites.clear()
        self.reports.clear()
        self.cases.clear()

    def remove(self, thing: StorableThing):
        self._do(thing, "remove")


class StoredThings(BaseModel):
    sent: _Things = Field(default_factory=_Things)
    received: _Things = Field(default_factory=_Things)

    def clear(self):
        self.sent.clear()
        self.received.clear()


THINGS = StoredThings()
