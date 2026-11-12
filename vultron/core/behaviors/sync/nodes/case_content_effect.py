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

"""Ledger effect slots for a case's vulnerability items and case references.

The CASE_MANAGER records each item or reference it brings into a case as one
``Add`` carrying the record in full, with the case as its target
(CLP-07-021).  A replica copies the record and lists it on its case, as the
entry states: it decides nothing (CM-23-016, CM-23-044).
"""

from typing import ClassVar, Literal

from py_trees.common import Status
from pydantic import ValidationError

from vultron.core.behaviors.sync.nodes._event_condition_base import (
    _SingleSemanticTypeNode,
)
from vultron.core.behaviors.sync.nodes._helpers import _LedgerEffectNode
from vultron.core.models._helpers import (
    _as_id,
    project_wire_snapshot_to_core,
)
from vultron.core.models.case_reference import CaseReference
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.vulnerability_item import VulnerabilityItem


class IsAddVulnerabilityItemEventNode(_SingleSemanticTypeNode):
    """Precondition: SUCCESS when this entry adds a vulnerability item.

    Per BTND-08-001, SYNC-12-001, CLP-07-021.
    """

    matched_semantic_type = (
        MessageSemantics.ADD_VULNERABILITY_ITEM_TO_CASE.value
    )


class IsAddCaseReferenceEventNode(_SingleSemanticTypeNode):
    """Precondition: SUCCESS when this entry adds a case reference.

    Per BTND-08-001, SYNC-12-001, CLP-07-021.
    """

    matched_semantic_type = MessageSemantics.ADD_CASE_REFERENCE_TO_CASE.value


class _ApplyCaseContentFromLedgerNode(_LedgerEffectNode):
    """Store the record an ``Add`` entry carries and list it on the case.

    Subclasses name the record class and the case list.  A record already
    held is kept, and one already listed is not listed twice, so a replayed
    entry changes nothing.  A replica that does not hold the case yet skips
    (Regime 2, ADR-0087); a snapshot whose ``object`` is not a valid record
    fails the node, so the entry is not persisted as applied (SYNC-12-004).
    """

    RECORD: ClassVar[type[VulnerabilityItem] | type[CaseReference]]
    FIELD: ClassVar[Literal["vulnerability_items", "case_references"]]

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = self._get_entry()
        try:
            record = self._carried_record(entry.payload_snapshot.get("object"))
        except (TypeError, ValidationError) as exc:
            self.feedback_message = (
                f"'{entry.semantic_type}' entry '{entry.id_}' carries no"
                f" valid {self.RECORD.__name__} inline: {exc}"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        case = self._resolve_case_replica(entry.case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica

        if self.datalayer.read(record.id_) is None:
            self.datalayer.create(record)
        listed = getattr(case, self.FIELD)
        if record.id_ in [_as_id(ref) for ref in listed]:
            self.logger.debug(
                "%s: '%s' already in case '%s' %s — idempotent no-op",
                self.name,
                record.id_,
                case.id_,
                self.FIELD,
            )
            return Status.SUCCESS
        # Assigned, not appended, so the case validates the new list.
        setattr(case, self.FIELD, [*listed, record.id_])
        self.datalayer.save(case)
        self.logger.info(
            "%s: listed %s '%s' on case '%s' from the ledger (CLP-07-021)",
            self.name,
            self.RECORD.__name__,
            record.id_,
            case.id_,
        )
        return Status.SUCCESS

    def _carried_record(
        self, data: object
    ) -> VulnerabilityItem | CaseReference:
        """The record *data* states inline.

        Raises:
            TypeError: *data* is not an inline object.
            ValidationError: *data* is not a valid record.
        """
        if not isinstance(data, dict):
            raise TypeError("the entry's object is not inline")
        return self.RECORD.model_validate(
            project_wire_snapshot_to_core(self.RECORD, data)
        )


class ApplyVulnerabilityItemFromLedgerNode(_ApplyCaseContentFromLedgerNode):
    """Copy an ``add_vulnerability_item_to_case`` entry's item (CLP-07-021)."""

    RECORD = VulnerabilityItem
    FIELD = "vulnerability_items"


class ApplyCaseReferenceFromLedgerNode(_ApplyCaseContentFromLedgerNode):
    """Copy an ``add_case_reference_to_case`` entry's reference (CLP-07-021)."""

    RECORD = CaseReference
    FIELD = "case_references"


__all__ = [
    "ApplyCaseReferenceFromLedgerNode",
    "ApplyVulnerabilityItemFromLedgerNode",
    "IsAddCaseReferenceEventNode",
    "IsAddVulnerabilityItemEventNode",
]
