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
#
# from pydantic import BaseModel, Field, ConfigDict
#
# from vultron.as_vocab.base.objects.activities.transitive import (
#     as_Offer,
#     as_Invite,
# )
# from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
# from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
#
# logger = logging.getLogger(__name__)
#
#
# class DuplicateKeyError(KeyError):
#     """Raised when attempting to add a duplicate key to the data layer."""
#
#
# class NoOverwriteDict(dict):
#     """Dictionary that raises an error on duplicate keys."""
#
#     def __setitem__(self, key, value):
#         if key in self:
#             raise DuplicateKeyError(f"Duplicate key: {key}")
#         super().__setitem__(key, value)
#
#     def update(self, *args, **kwargs):
#         for k, v in dict(*args, **kwargs).items():
#             if k in self:
#                 raise DuplicateKeyError(f"Duplicate key: {k}")
#             super().__setitem__(k, v)
#
#
# class OfferStatus(StrEnum):
#     """Enumeration of possible Offer statuses."""
#
#     RECEIVED = auto()
#     ACCEPTED = auto()
#     TENTATIVE_REJECTED = auto()
#     REJECTED = auto()
#
#
# class OfferWrapper(BaseModel):
#     """Wrapper for objects stored in the data layer."""
#
#     object_id: str = Field(..., description="The ID of the Offer object.")
#     object_: as_Offer = Field(..., description="The Offer object.")
#     object_status: OfferStatus = Field(
#         default=OfferStatus.RECEIVED,
#         description="The status of the Offer object.",
#     )
#
#
# class InviteWrapper(OfferWrapper):
#     """Wrapper for Invite objects stored in the data layer."""
#
#     object_: as_Invite = Field(..., description="The Invite object.")
#
#
# @runtime_checkable
# class DataLayer(Protocol):
#     """Protocol for a Vultron Data Layer."""
#
#     def receive_offer(self, offer: as_Offer) -> None:
#         """Receive an offer into the data layer."""
#         ...
#
#     def receive_report(self, report: VulnerabilityReport) -> None:
#         """Receive a report into the data layer."""
#         ...
#
#     def receive_case(self, case: VulnerabilityCase) -> None:
#         """Receive a case into the data layer."""
#         ...
#
#     def get_all_offers(self) -> list[as_Offer]:
#         """Get all offers from the data layer."""
#         ...
#
#     def get_all_reports(self) -> list[VulnerabilityReport]:
#         """Get all reports from the data layer."""
#         ...
#
#     def get_report_by_id(self, report_id: str) -> VulnerabilityReport | None:
#         """Get a report by ID from the data layer."""
#         ...
#
#
# class Collection(BaseModel):
#     """In-Memory Collection for objects."""
#
#     model_config = ConfigDict(arbitrary_types_allowed=True)
#
#     things: NoOverwriteDict[str, object] = Field(
#         default_factory=NoOverwriteDict,
#         description="Dictionary of unique generic objects.",
#     )
#     offers: NoOverwriteDict[str, OfferWrapper] = Field(
#         default_factory=NoOverwriteDict,
#         description="Dictionary of unique offer objects.",
#     )
#     invites: list[InviteWrapper] = Field(default_factory=list)
#     reports: NoOverwriteDict[str, VulnerabilityReport] = Field(
#         default_factory=NoOverwriteDict,
#         description="Dictionary of unique report objects.",
#     )
#     cases: list[VulnerabilityCase] = Field(default_factory=list)
#
#
# class MemoryStore(BaseModel):
#     """In-Memory Store for received objects."""
#
#     model_config = ConfigDict(arbitrary_types_allowed=True)
#     received: Collection = Field(default_factory=Collection)
#
#     def clear(self) -> None:
#         """Clear all stored objects."""
#         logger.debug("Clearing in-memory store")
#         self.received = Collection()
#
#
# _THINGS = MemoryStore()
# """Global In-Memory Store Instance."""
#
#
# def wrap_offer(offer: as_Offer) -> OfferWrapper:
#     """Wrap an Offer object for storage."""
#     logger.debug("Wrapping offer %s...", offer.model_dump_json()[:30])
#     return OfferWrapper(
#         object_id=offer.as_id,
#         object_=offer,
#         object_status=OfferStatus.RECEIVED,
#     )
#
#
# class InMemoryDataLayer(DataLayer):
#     """In-Memory Implementation of the Data Layer."""
#
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self._things = _THINGS
#
#     def receive_offer(self, offer: as_Offer) -> None:
#         wrapped = wrap_offer(offer)
#         logger.debug("Receiving offer %s...", wrapped.object_id)
#         try:
#             self._things.received.things[wrapped.object_id] = wrapped
#         except DuplicateKeyError:
#             logger.debug("Duplicate offer rejected: %s", wrapped.object_id)
#             raise ValueError(f"Duplicate offer: {wrapped.object_id}")
#
#     def receive_report(self, report: VulnerabilityReport) -> None:
#         logger.debug("Receiving report %s...", report.as_id)
#         try:
#             self._things.received.things[report.as_id] = report
#         except DuplicateKeyError:
#             logger.debug("Duplicate report rejected: %s", report.as_id)
#             raise ValueError(f"Duplicate report: {report.as_id}")
#
#     def receive_case(self, case: VulnerabilityCase) -> None:
#         logger.debug("Receiving case %s...", case.as_id)
#         self._things.received.things.append(case)
#
#     def get_all_offers(self) -> list[as_Offer]:
#         logger.debug("Retrieving all offers from the data layer.")
#         offers = [
#             wrapped.object_
#             for wrapped in self._things.received.things.values()
#         ]
#         return offers
#
#     def get_offer_by_id(self, offer_id: str) -> as_Offer | None:
#         logger.debug("Retrieving offer by ID: %s", offer_id)
#         wrapped = self._things.received.things.get(offer_id, None)
#
#         if wrapped is not None:
#             return wrapped.object_
#         return None
#
#     def get_all_reports(self) -> list[VulnerabilityReport]:
#         logger.debug("Retrieving all reports from the data layer.")
#         reports = [
#             x
#             for x in self._things.received.things.values()
#             if isinstance(x, VulnerabilityReport)
#         ]
#         return reports
#
#     def get_all_cases(self) -> list[VulnerabilityCase]:
#         logger.debug("Retrieving all cases from the data layer.")
#
#         cases = [
#             x
#             for x in self._things.received.things.values()
#             if isinstance(x, VulnerabilityCase)
#         ]
#
#         return cases
#
#     def get_report_by_id(self, report_id: str) -> VulnerabilityReport | None:
#         logger.debug("Retrieving report by ID: %s", report_id)
#         return self._things.received.things.get(report_id, None)
#
#
# def get_datalayer() -> DataLayer:
#     """Get the data layer instance."""
#     # For now, we just return an in-memory backend.
#     # in the future, this could be extended to return different backends
#     # based on configuration or environment variables.
#     logger.debug("Providing InMemoryDataLayer instance.")
#     return InMemoryDataLayer()
