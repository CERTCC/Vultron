#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
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

# !/usr/bin/env python
"""
The `vultron.errors` module provides exceptions for Vultron
"""


class VultronError(Exception):
    """Base class for all Vultron exceptions"""


class VultronNotFoundError(VultronError):
    """Raised when a requested resource cannot be found."""

    def __init__(self, resource_type: str, resource_id: str):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(f"{resource_type} '{resource_id}' not found.")


class VultronInvalidStateTransitionError(VultronError):
    """Raised when an operation requests an invalid state machine transition."""

    def __init__(self, message: str, activity_id: str | None = None):
        self.activity_id = activity_id
        super().__init__(message)


# Deprecated alias — use VultronInvalidStateTransitionError instead.
VultronConflictError = VultronInvalidStateTransitionError


class VultronValidationError(VultronError):
    """Raised when domain validation of a resource or request fails."""

    def __init__(self, message: str, activity_id: str | None = None):
        self.activity_id = activity_id
        super().__init__(message)


class VultronApiHandlerNotFoundError(VultronError, KeyError):
    """Raised when no handler is found for a given activity type."""


class VultronOutboxObjectIntegrityError(VultronError):
    """Raised when an outbound activity's object_ is a bare string URI or
    Link reference instead of the required inline domain object.

    Outbound initiating activities (Create, Offer, Invite, Announce, Add,
    Remove, etc.) MUST carry a fully inline typed object so that recipients
    can determine the semantic type — because the recipient has no access to
    the sender's DataLayer.  See specs/actor-knowledge-model.md AKM-03-001,
    specs/message-validation.md MV-09-001, MV-09-002.
    """

    def __init__(
        self,
        message: str,
        activity_id: str | None = None,
        activity_type: str | None = None,
    ):
        self.activity_id = activity_id
        self.activity_type = activity_type
        super().__init__(message)


class CvdStateModelError(VultronError):
    """Base class for errors in the CVD state model."""


class CVDmodelError(CvdStateModelError):
    pass


class ScoringError(CvdStateModelError):
    pass


class ValidationError(CvdStateModelError):
    pass


class PatternValidationError(ValidationError):
    pass


class StateValidationError(ValidationError):
    pass


class HistoryValidationError(ValidationError):
    pass


class TransitionValidationError(ValidationError):
    pass
