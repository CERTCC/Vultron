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

"""Case creation nodes for the report behavior tree."""

from typing import Any

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.activity import VultronCreateCaseActivity
from vultron.core.models.case import VultronCase


def _append_addressee_ids(addressees: list[str], value: object) -> None:
    if value is None:
        return
    if isinstance(value, str):
        addressees.append(value)
        return
    if isinstance(value, list):
        for item in value:
            _append_addressee_ids(addressees, item)
        return
    addressee_id = getattr(value, "id_", None)
    if isinstance(addressee_id, str):
        addressees.append(addressee_id)


def _collect_create_case_addressees(
    actor: object,
    report: object,
    offer: object,
    actor_id: str,
) -> list[str]:
    addressees: list[str] = []
    for value in (
        actor,
        getattr(report, "attributed_to", None) if report is not None else None,
        getattr(offer, "to", None) if offer is not None else None,
        getattr(offer, "actor", None) if offer is not None else None,
    ):
        _append_addressee_ids(addressees, value)
    return [
        addressee for addressee in set(addressees) if addressee != actor_id
    ]


class CreateCaseNode(DataLayerAction):
    """
    Create VulnerabilityCase from validated report.

    Creates a new VulnerabilityCase containing the validated report and persists
    it to the DataLayer. Stores the case ID in the blackboard for subsequent nodes.

    This node implements case creation from the validate_report handler.

    Note: Named CreateCaseNode (not CreateCaseActivity) to avoid conflict with
    as_CreateCase activity class.
    """

    def __init__(self, report_id: str, name: str | None = None):
        """
        Initialize CreateCaseNode.

        Args:
            report_id: ID of VulnerabilityReport to include in case
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id

    def update(self) -> Status:
        """
        Create VulnerabilityCase and persist to DataLayer.

        Returns:
            SUCCESS if case created, FAILURE on error
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            report_obj = self.datalayer.read(
                self.report_id, raise_on_missing=True
            )
            if report_obj is None:
                self.logger.error(
                    f"{self.name}: Report {self.report_id} not found"
                )
                return Status.FAILURE

            report_id_ref = report_obj.id_
            case = VultronCase(
                name=f"Case for Report {self.report_id}",
                vulnerability_reports=[report_id_ref],
                attributed_to=self.actor_id,
            )

            try:
                self.datalayer.create(case)
                self.logger.info(
                    f"{self.name}: Created VulnerabilityCase {case.id_}: {case.name}"
                )
            except ValueError as e:
                self.logger.warning(
                    f"{self.name}: VulnerabilityCase {case.id_} already exists: {e}"
                )

            self.blackboard.register_key(
                key="case_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.case_id = case.id_

            return Status.SUCCESS

        except Exception as e:
            self.logger.error(f"{self.name}: Error creating case: {e}")
            return Status.FAILURE


class CreateCaseActivity(DataLayerAction):
    """
    Create CreateCaseActivity activity for case creation notification.

    Generates a CreateCaseActivity activity to notify relevant actors about the new case.
    Collects addressees from actor, report.attributed_to, and offer.to fields.

    This node implements activity generation from the validate_report handler.
    """

    def __init__(self, report_id: str, offer_id: str, name: str | None = None):
        """
        Initialize CreateCaseActivity node.

        Args:
            report_id: ID of VulnerabilityReport (for addressee collection)
            offer_id: ID of Offer (for addressee collection)
            name: Optional custom node name (defaults to class name)
        """
        super().__init__(name=name or self.__class__.__name__)
        self.report_id = report_id
        self.offer_id = offer_id

    def setup(self, **kwargs: Any) -> None:
        """Set up blackboard access including case_id key."""
        super().setup(**kwargs)
        self.blackboard.register_key(
            key="case_id", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            key="commit_activity_id", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            key="activity", access=py_trees.common.Access.WRITE
        )

    def update(self) -> Status:
        """
        Create CreateCaseActivity activity and persist to DataLayer.

        Returns:
            SUCCESS if activity created, FAILURE on error
        """
        if self.datalayer is None or self.actor_id is None:
            self.logger.error(
                f"{self.name}: DataLayer or actor_id not available"
            )
            return Status.FAILURE

        try:
            case_id = self.blackboard.get("case_id")
            if case_id is None:
                self.logger.error(
                    f"{self.name}: case_id not found in blackboard"
                )
                return Status.FAILURE

            actor = self.datalayer.read(self.actor_id, raise_on_missing=True)
            report = self.datalayer.read(self.report_id, raise_on_missing=True)
            offer = self.datalayer.read(self.offer_id)
            addressees = _collect_create_case_addressees(
                actor, report, offer, self.actor_id
            )
            self.logger.info(
                f"{self.name}: Notifying addressees: {addressees}"
            )

            case_obj = self.datalayer.read(case_id)
            create_case_activity = VultronCreateCaseActivity(
                actor=self.actor_id,
                object_=case_obj if case_obj is not None else case_id,
                context=case_id,
                to=addressees if addressees else None,
            )

            try:
                self.datalayer.create(create_case_activity)
                self.logger.info(
                    f"{self.name}: Created CreateCaseActivity activity: {create_case_activity.id_}"
                )
            except ValueError as e:
                self.logger.warning(
                    f"{self.name}: CreateCaseActivity activity {create_case_activity.id_} already exists: {e}"
                )

            self.blackboard.register_key(
                key="activity_id", access=py_trees.common.Access.WRITE
            )
            self.blackboard.commit_activity_id = create_case_activity.id_
            self.blackboard.activity = create_case_activity
            self.blackboard.activity_id = create_case_activity.id_
            return Status.SUCCESS

        except Exception as e:
            self.logger.error(
                f"{self.name}: Error creating CreateCaseActivity activity: {e}"
            )
            return Status.FAILURE
