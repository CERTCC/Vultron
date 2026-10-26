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

from collections.abc import Iterable, Sequence
from typing import NamedTuple


class Violation(NamedTuple):
    """One violated rule in a rejection that reports every violation.

    A validation boundary that refuses its input as a unit still owes its
    caller every violation it can recognise (EH-07-001).  This is the unit of
    that report: the rule's human-readable ``message``, the ``dimensions`` the
    rule reads, and whether it is a root cause or a consequence of another
    reported violation (EH-07-002).

    ``derived`` is a property of the *set*, not of the rule on its own, so it
    is assigned by whichever evaluator produced the complete list — see
    :func:`~vultron.core.states.participant_transitions\
    .participant_transition_violations`.
    """

    message: str
    dimensions: tuple[str, ...] = ()
    derived: bool = False

    @property
    def classification(self) -> str:
        """``"derived"`` or ``"root"`` — the EH-07-002 label for this rule."""
        return "derived" if self.derived else "root"


def _render_violations(header: str, violations: Sequence[Violation]) -> str:
    """Return *header* followed by one indented line per violation.

    One rendering serves both contracts: the whole set in ``str()`` (EH-07-003)
    and the whole set in an HTTP ``message`` field (EH-05-002), which is
    ``str()`` of the same exception.
    """
    lines = [f"{header} ({len(violations)} violation(s)):"]
    lines.extend(f"  [{v.classification}] {v.message}" for v in violations)
    return "\n".join(lines)


class VultronError(Exception):
    """Base class for all Vultron exceptions"""


class CarriesViolations:
    """Mixin: structured multi-violation carriage for a ``VultronError``.

    EH-07-003 requires an exception raised for more than one violation to keep
    them as structured data and to render the whole set in ``str()``, so no
    caller parses a joined message.  Subclasses set ``self.violations`` in
    ``__init__``; this mixin owns the rendering.  It must precede
    :class:`VultronError` in the bases so its ``__str__`` wraps
    ``Exception.__str__``.
    """

    violations: tuple[Violation, ...] = ()

    def __str__(self) -> str:
        summary = super().__str__()
        if not self.violations:
            return summary
        return _render_violations(summary, self.violations)


class VultronNotFoundError(VultronError):
    """Raised when a requested resource cannot be found."""

    def __init__(self, resource_type: str, resource_id: str):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(f"{resource_type} '{resource_id}' not found.")


class VultronNotACaseParticipantError(VultronError):
    """Raised when an actor asks to read a case it is no active participant of.

    The case host serves a case's objects only to the case's active
    participants (AKM-05-006, CM-10-004).  The requester is the actor the
    request claims to be: the prototype authenticates nobody (#509).
    """

    def __init__(self, case_id: str, actor_id: str):
        self.case_id = case_id
        self.actor_id = actor_id
        super().__init__(
            f"Actor '{actor_id}' is not an active participant of case"
            f" '{case_id}'."
        )


class VultronAlreadyExistsError(VultronError, ValueError):
    """Raised when creating a record whose ``id_`` is already present.

    The counterpart of :exc:`VultronNotFoundError`, and the *only* cause a
    caller of ``DataLayer.create()`` may legitimately swallow: the record it
    wanted stored is already stored.

    This type exists so that "already there" stays separable from "could not be
    projected".  ``crud.create`` previously raised a bare ``ValueError`` for the
    duplicate, and every caller that swallows a duplicate catches it — so any
    *other* ``ValueError`` escaping the same call was silently logged as a
    benign duplicate and never stored.  That is not hypothetical: it is why
    :exc:`VultronValidationError` was kept out of the ``ValueError`` hierarchy,
    and it also swallowed ``Record.from_obj``'s two genuine faults (an object
    with no ``type_``, and a ``type_`` still carrying the ``as_`` prefix).

    ``ValueError`` remains in the base classes so that callers written against
    the older contract keep working; callers that mean *only* "already exists"
    MUST catch this class rather than ``ValueError``.  ARCH-23-006's note
    records why :exc:`VultronValidationError` must be absorbable by Pydantic,
    which is what made the shared base untenable.
    """


class VultronInvalidStateTransitionError(VultronError):
    """Raised when an operation requests an invalid state machine transition."""

    def __init__(self, message: str, activity_id: str | None = None):
        self.activity_id = activity_id
        super().__init__(message)


class VultronEntryRefusedError(VultronInvalidStateTransitionError):
    """Raised when a ledger entry does not apply to the case it is applied to.

    The one apply function checks the starting state an entry implies before
    it writes what the entry carries (ADR-0124, CM-23-016).  On a replica a
    refusal means an earlier entry is missing or the replica's case has
    diverged, so the Announce that carried the entry is held for gap handling
    (SYNC-14-001) and the entry is never patched over.  On the CASE_MANAGER a
    refused trial apply stops the act before anything is committed.
    """


# Deprecated alias — use VultronInvalidStateTransitionError instead.
VultronConflictError = VultronInvalidStateTransitionError


class VultronValidationError(CarriesViolations, VultronError, ValueError):
    """Raised when domain validation of a resource or request fails.

    When the boundary recognised more than one violation, pass them as
    ``violations``: they are kept as structured data on the exception and
    ``str()`` renders the whole set (via :class:`CarriesViolations`), so no
    caller has to parse the joined message to recover the individual rules
    (EH-07-003).  This follows :exc:`DemoFailureError`'s shape, the house
    pattern for accumulate-all-then-fail (DEMOCI-01-003).

    ``ValueError`` is in the base classes for the same reason as
    :exc:`VultronProtocolViolationError` and
    :exc:`VultronReferenceResolutionError`: Pydantic absorbs a ``ValueError``
    raised inside a validator and reports it as a failed branch, where any other
    exception escapes the whole ``model_validate()`` call.  ARCH-23-006 requires
    this: under ADR-0099 core classes sit *inside* wire unions, so a core-side
    guard firing while Pydantic resolves a union must fail that branch rather
    than abort the operation.  The rule's note names this as the defect to fix
    before the rule is inverted, and inverting it is what ADR-0099 does.

    This class deliberately did *not* inherit ``ValueError`` until
    :exc:`VultronAlreadyExistsError` existed, because ``crud.create`` signalled
    a duplicate row with a bare ``ValueError`` that callers swallow — so sharing
    the base made a projection failure indistinguishable from "already stored".
    Separability now comes from the two distinct types, not from this class
    avoiding ``ValueError``; see
    ``test_normalization_failure_is_distinguishable_from_duplicate_row``.
    """

    def __init__(
        self,
        message: str,
        activity_id: str | None = None,
        violations: Iterable[Violation] | None = None,
    ):
        self.activity_id = activity_id
        self.violations = tuple(violations or ())
        super().__init__(message)


class VultronNotAnEmbargoError(VultronValidationError):
    """Raised when an embargo id resolves to a record that is not an ``EmbargoEvent``.

    The type-mismatch half of the fail-closed embargo read (EMB-18-003); the
    missing half is :exc:`VultronNotFoundError`.  It carries ``embargo_id`` so
    a caller can tell *which* embargo was unreadable — for example the one a
    revision replaces, as opposed to the one it activates — without parsing
    the message.
    """

    def __init__(self, embargo_id: str, record_type: str):
        self.embargo_id = embargo_id
        self.record_type = record_type
        super().__init__(
            f"Embargo '{embargo_id}' is not an EmbargoEvent (got {record_type})."
        )


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

    This codebase carries the ``object`` of every outbound activity as a fully
    inline typed object so that recipients can determine the semantic type
    without dereferencing it, which this codebase does only in a few cases
    (AKM-05-007).  The
    protocol allows the object inline or by reference (AKM-03-001, MV-09-001);
    inlining is this codebase's rule (AKM-03-003), enforced at delivery
    (AKM-03-002, MV-09-002).
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


class VultronProtocolViolationError(
    CarriesViolations, VultronError, ValueError
):
    """Raised when an inbound protocol message violates a mandatory requirement.

    The inbound mirror of :exc:`VultronOutboxObjectIntegrityError`.  While
    that class catches outbound integrity failures (sending a bare URI when an
    inline object is required), this class catches inbound structural
    violations — messages received that break a MUST-level spec requirement.

    First use: CBT-05-008 — bootstrap ``Create(VulnerabilityCase)`` carrying a
    participant as a bare URI string rather than a fully inline typed object.
    Receivers MUST raise this error and reject the bootstrap rather than
    silently synthesising participant state from domain knowledge.

    ``ValueError`` is included in the base classes so that Pydantic absorbs
    this error when it is raised from a ``model_validator`` or
    ``field_validator`` and wraps it in a ``ValidationError`` rather than
    letting it escape the ``model_validate()`` call.  Callers that need to
    distinguish a protocol violation from an ordinary validation failure can
    inspect ``ValidationError.errors()[0]['ctx']['error']``.

    A boundary that recognised more than one violation passes them as
    ``violations`` (EH-07-003) — first use: ``CoreObject``'s computed-field
    contradiction check (ARCH-23-005), which names every contradicted field.
    """

    def __init__(
        self,
        message: str,
        violations: Iterable[Violation] | None = None,
    ):
        self.violations = tuple(violations or ())
        super().__init__(message)


class VultronReusedActivityIdError(VultronProtocolViolationError):
    """Raised when a delivery reuses a held activity id with a different body.

    An activity id names one activity (ID-01-001), so a second body under an
    id the receiver already holds is not a redelivery: it is refused at
    ingress and neither body is routed (IE-10-002).  The comparison is an
    exact match of the sealed received texts (VM-08-002).

    The message names the reused id, which becomes the inbox outcome's
    ``failure_reason``; the sending actor is kept on :attr:`actor_id` for the
    WARNING the ingress adapter logs.

    Args:
        activity_id: The id the delivery reuses.
        actor_id: The sending actor the delivery names, if any.
    """

    def __init__(self, activity_id: str, actor_id: str | None):
        self.activity_id = activity_id
        self.actor_id = actor_id
        super().__init__(
            f"activity id '{activity_id}' is reused with a different body"
            " than the one held for it, so the delivery is refused"
            " (IE-10-002)"
        )


class VultronReferenceResolutionError(VultronError, ValueError):
    """Raised when an IRI reference in an object-only slot cannot be materialised.

    VM-06-007 makes ``rehydrate()`` the sole owner of ID-to-object
    materialisation and requires it to *refuse* rather than fabricate a
    placeholder.  This is that refusal.  It fires for two distinct causes, both
    of which mean the slot cannot legally be filled:

    * the reference resolved to nothing in the data layer, or
    * it resolved to something that is not an AS2 object, so it cannot go into a
      wire slot.

    ``ValueError`` is included in the base classes for the same reason as
    :exc:`VultronProtocolViolationError`: so Pydantic absorbs the error and
    wraps it in a ``ValidationError`` if it is ever raised inside a validator,
    rather than escaping the whole ``model_validate()`` call.  ARCH-23-006's
    note records what goes wrong when a core-side guard is *not* absorbable that
    way.
    """


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


class TriggerRegistryError(VultronError):
    """Raised when the trigger registry cannot be assembled consistently.

    Raised at import time by ``vultron.trigger_registry`` when two rows share
    a verb, when a row's ``request_model`` binds a result type other than the
    row's ``result_type``, or when a request model is shared by rows that
    disagree on the use case or result type — a table that cannot resolve a
    request to one use case (ADR-0110, TRIG-12-004).  Fails fast so a bad row
    is impossible to miss, as ``RegistryOrderError`` does for the received side.
    """


class BtNodePreconditionError(VultronError):
    """Raised by a BT node helper when a required precondition is unmet.

    BT node helper methods (private methods called from ``update()``) MUST
    raise this exception instead of returning ``None`` when a precondition
    fails.  ``update()`` is the single ``try/except`` handler that converts
    the exception to ``Status.FAILURE`` and sets ``self.feedback_message``.
    See ADR-0032 and ``notes/bt-integration.md`` BT-HELPER-01.
    """


class VultronWiringError(VultronError):
    """Raised when a node is missing a DataLayer or port it requires.

    That is a deployment or composition fault, never the sender's doing, so
    ``BTBridge`` flags it as ``internal_error`` even though it is a
    ``VultronError`` — and a received handler therefore raises rather than
    reporting the message as ``REFUSED`` (#2255, ADR-0095).
    """


class VultronReadOnlyViewError(VultronError, AttributeError):
    """Raised on an attempt to change a read-only view of a received activity.

    A received activity's view is parsed fresh from the archived body on
    every load (ADR-0149), so a change to it could only ever reach that one
    copy, and would read as a change to what arrived.  Core changes its own
    records instead.  An ``AttributeError``, as assignment to any frozen
    object raises.
    """


class VultronUnhostedActorError(VultronWiringError):
    """Raised when execution is scoped to an actor this container does not host.

    A store can be opened only for an actor under the authority of the store
    in hand: ``clone_for_actor`` on another authority's actor would mint an
    empty local store in its name.  No sanctioned path executes a tree, or
    enqueues an activity, as an actor the running container does not host
    (BT-05-005, CM-24-004, CLP-10-014, ADR-0109), so reaching one is a
    composition fault, not a protocol outcome.
    """


class VultronStaleStoreError(VultronError):
    """Raised when a persisted store predates a change to its stored shape.

    Stored data carries no backwards compatibility and no migration: a store
    written before a shape change is refused when it is opened, with a message
    saying it must be reset, rather than run without the guarantee the new
    shape provides (``notes/datalayer-design.md`` § "Changing a Table's Shape").
    """


class VultronBTInternalError(VultronError):
    """Raised when a received-side or trigger-side BT failed on an internal error.

    ``BTBridge`` catches a non-``VultronError`` exception escaping a node and
    reports it as ``FAILURE`` with ``internal_error=True``.  That is a
    programming error, not a protocol outcome, so a handler MUST NOT report it
    as ``HandlerDisposition.REFUSED`` (ADR-0095): it re-raises it as this
    exception so the inbox pipeline records it as a raised dispatch, traceback
    and all, and it stays distinguishable from a refusal.  A trigger raises it
    for the same reason, so a server-side fault is never translated into the
    client's 422.
    """


#: The ``VultronError`` subclasses that are our own fault, never a protocol
#: outcome: a composition fault and an internal error carried across a
#: nested bridge.  ``BTBridge`` flags both as ``internal_error``, so a node
#: that turns a ``VultronError`` into a refusal re-raises these first: a
#: refusal is answered to the sender (CLP-05-001), an internal failure never
#: is (ADR-0095).
INTERNAL_FAULTS: tuple[type[VultronError], ...] = (
    VultronWiringError,
    VultronBTInternalError,
)


class DemoScenarioRegistryError(VultronError):
    """Raised when a demo scenario's self-registration is invalid.

    Raised at import time by the ``@scenario`` decorator in
    ``vultron.demo.scenario.registry`` — a malformed spec, a name already
    registered with a different spec, or a declared name that contradicts the
    module it was declared in — and by ``discover_scenarios()`` when a
    discovered ``*_demo`` module registered nothing at all.

    Fails fast for the same reason :class:`RegistryOrderError` does: every
    committed scenario artifact is generated from this registry, so a registry
    that is quietly wrong yields tables and a CI matrix that look complete and
    are not.  See ``specs/demo-ci.yaml`` DEMOCI-11 and ADR-0098.
    """


class DemoActorRoleError(VultronError):
    """Raised when a scenario's ``ActorRole`` declaration is invalid.

    Raised at import time by :class:`~vultron.demo.helpers.actor_roles.ActorRole`
    and :func:`~vultron.demo.helpers.actor_roles.role_map` — a malformed role
    name, a missing help string, id metadata on a role that declares no ``--*-id``
    option, or two roles in one scenario sharing a name or a container env var.

    Fails fast for the same reason :class:`DemoScenarioRegistryError` does: the
    role list is what generates a scenario's CLI options *and* what its
    ``main()`` signature is ratcheted against (DEMOCI-11-011), so a role list
    that is quietly wrong yields a sub-command whose options look complete and
    point at the wrong container.
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

    def __str__(self) -> str:
        lines = [f"{len(self.failures)} demo failure(s):"]
        lines.extend(f"  {f}" for f in self.failures)
        return "\n".join(lines)
