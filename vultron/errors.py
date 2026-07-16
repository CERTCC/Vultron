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


class VultronCanonicalEntryError(VultronError):
    """Raised when a case-ledger entry violates canonical entry criteria."""


class VultronApiHandlerNotFoundError(VultronError, KeyError):
    """Raised when no handler is found for a given activity type."""


class VultronOutboxToFieldMissingError(VultronError):
    """Raised when an outbound activity lacks a non-empty ``to:`` field.

    All Vultron protocol exchanges are direct messages.  Every outbound
    activity MUST address at least one recipient via ``to:``.
    See specs/outbox.yaml OX-08-001, OX-08-002, OX-08-003.
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


class VultronOutboxObjectIntegrityError(VultronError):
    """Raised when an outbound activity's object_ is a bare string URI or
    Link reference instead of the required inline domain object.

    Outbound initiating activities (Create, Offer, Invite, Announce, Add,
    Remove, etc.) MUST carry a fully inline typed object so that recipients
    can determine the semantic type — because the recipient has no access to
    the sender's DataLayer.  See specs/actor-knowledge-model.yaml AKM-03-001,
    specs/message-validation.yaml MV-09-001, MV-09-002.
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


class VultronActivityConstructionError(VultronError):
    """Raised when a factory function cannot construct the requested activity.

    Wraps a Pydantic ``ValidationError`` as ``__cause__`` so that callers
    can inspect the original validation details if needed.  Factory
    functions MUST catch ``pydantic.ValidationError`` and re-raise as this
    exception to keep internal activity class names out of public error
    messages.  See ``specs/activity-factories.yaml`` AF-04-001, AF-04-002.
    """


class RegistryOrderError(VultronError):
    """Raised when ``SEMANTIC_REGISTRY`` contains a less-specific pattern
    that precedes a more-specific one in the same ``activity_`` group.

    Raised at import time by ``_validate_registry_order()`` in
    ``vultron.semantic_registry`` so that ordering violations fail fast and
    are impossible to miss.  See ``specs/semantic-extraction.yaml`` SE-03-002
    and ``vultron/wire/as2/AGENTS.md``.
    """


class UnroutableActivityError(VultronError):
    """Raised when an inbound activity cannot be routed to a case.

    Raised by the dispatcher when no ``case_id`` can be extracted from an
    inbound event whose semantic type requires case-scoped join-backfill
    gating.  The caller MUST handle this exception explicitly rather than
    silently dropping the activity.  See ``specs/architecture.yaml``
    ARCH-15-003 and ``notes/domain-validation.md``.
    """

    def __init__(self, activity_id: str, reason: str):
        self.activity_id = activity_id
        self.reason = reason
        super().__init__(f"Activity '{activity_id}' is unroutable: {reason}")


class BtNodePreconditionError(VultronError):
    """Raised by a BT node helper when a required precondition is unmet.

    BT node helper methods (private methods called from ``update()``) MUST
    raise this exception instead of returning ``None`` when a precondition
    fails.  ``update()`` is the single ``try/except`` handler that converts
    the exception to ``Status.FAILURE`` and sets ``self.feedback_message``.
    See ADR-0032 and ``notes/bt-integration.md`` BT-HELPER-01.
    """


class DemoFailureError(VultronError):
    """Raised when a demo scenario completes with one or more step failures.

    Accumulates all failures from ``demo_step`` and ``demo_check`` context
    managers in ``vultron.demo.utils``.  Raised by ``assert_demo_success()``
    at the end of a scenario run so that ``docker compose --exit-code-from``
    can detect failure.  See ``specs/demo-ci.yaml`` DEMOCI-01-001,
    DEMOCI-01-005.
    """

    def __init__(self, message: str, failures: list[str]) -> None:
        super().__init__(message)
        self.failures = failures
