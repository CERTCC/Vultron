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

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from vultron.as_vocab.base.objects.activities.transitive import (
    as_Offer,
    as_Invite,
)
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport


@runtime_checkable
class DataLayer(Protocol):
    """Protocol for a Vultron Data Layer."""

    def receive_offer(self, offer: as_Offer) -> None:
        """Receive an offer into the data layer."""
        ...

    def receive_report(self, report: VulnerabilityReport) -> None:
        """Receive a report into the data layer."""
        ...

    def receive_case(self, case: VulnerabilityCase) -> None:
        """Receive a case into the data layer."""
        ...

    def get_all_offers(self) -> list[as_Offer]:
        """Get all offers from the data layer."""
        ...

    def get_all_reports(self) -> list[VulnerabilityReport]:
        """Get all reports from the data layer."""
        ...


class Collection(BaseModel):
    """In-Memory Collection for objects."""

    offers: list[as_Offer] = Field(default_factory=list)
    invites: list[as_Invite] = Field(default_factory=list)
    reports: list[VulnerabilityReport] = Field(default_factory=list)
    cases: list[VulnerabilityCase] = Field(default_factory=list)


class MemoryStore(BaseModel):
    """In-Memory Store for received objects."""

    received: Collection = Field(default_factory=Collection)

    def clear(self) -> None:
        """Clear all stored objects."""
        self.received = Collection()


_THINGS = MemoryStore()
"""Global In-Memory Store Instance."""


class InMemoryDataLayer(DataLayer):
    """In-Memory Implementation of the Data Layer."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._things = _THINGS

    def receive_offer(self, offer: as_Offer) -> None:
        self._things.received.offers.append(offer)

    def receive_report(self, report: VulnerabilityReport) -> None:
        self._things.received.reports.append(report)

    def receive_case(self, case: VulnerabilityCase) -> None:
        self._things.received.cases.append(case)

    def get_all_offers(self) -> list[as_Offer]:
        return self._things.received.offers

    def get_all_reports(self) -> list[VulnerabilityReport]:
        return self._things.received.reports

    def get_all_cases(self) -> list[VulnerabilityCase]:
        return self._things.received.cases


def get_datalayer() -> DataLayer:
    """Get the data layer instance."""
    # For now, we just return an in-memory backend.
    # in the future, this could be extended to return different backends
    # based on configuration or environment variables.
    return InMemoryDataLayer()
