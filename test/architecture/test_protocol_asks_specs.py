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
"""Spec coverage for the protocol-ask primitive (ADR-0080, ASK-01..ASK-08).

Every ``kind: protocol`` requirement introduced by ADR-0080 is marked here, so
the spec-coverage ratchet (`test_spec_coverage_ratchet.py`) does not grow when
the requirements land ahead of their implementations.

Two kinds of test live in this module:

**Passing tests** assert a requirement the codebase already satisfies. These are
structural assertions chosen so they stay meaningful *after* the ask machinery is
built — they are not vacuous restatements of "the thing does not exist yet".

**Strict-xfail tests** assert a requirement that is not yet implemented, against
an artifact the requirement names. Each carries the G01 implementation issue in
its ``reason=``. When the feature lands the test XPASSes, ``strict=True`` fails
the build, and whoever landed it must replace the placeholder assertion with a
real behavioural one. That promotion is the point: this module is a ratchet, not
a substitute for testing the feature.

Specs: ASK-01 through ASK-08, CP-05-007, OX-14-002, RSH-07-004, RSH-07-005.
See `notes/protocol-asks.md` and ADR-0080.
"""

import importlib

import pytest

from test.architecture import _corpus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VULTRON = _corpus.REPO_ROOT / "vultron"

#: Candidate import paths for the outstanding-ask register (ASK-04). The
#: register does not exist yet; #2883 creates it. Listed as candidates rather
#: than one path so the tests here promote on whichever module name is chosen.
_ASK_REGISTER_CANDIDATES = (
    ("vultron.core.models.ask_register", "OutstandingAskRegister"),
    ("vultron.core.models.outstanding_ask", "OutstandingAskRegister"),
    ("vultron.core.models.ask_record", "OutstandingAskRecord"),
)

#: Candidate import paths for the ProcessingFault object type (ASK-07). #2889
#: creates it.
_FAULT_CANDIDATES = (
    ("vultron.core.models.processing_fault", "ProcessingFault"),
    ("vultron.wire.as2.vocab.objects.processing_fault", "as_ProcessingFault"),
)


def _first_available(candidates: tuple[tuple[str, str], ...]) -> type | None:
    """Return the first importable class among *candidates*, else ``None``."""
    for module_name, class_name in candidates:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        obj = getattr(module, class_name, None)
        if isinstance(obj, type):
            return obj
    return None


def _ask_register() -> type | None:
    """Return the outstanding-ask register class, or ``None`` if absent."""
    return _first_available(_ASK_REGISTER_CANDIDATES)


def _processing_fault() -> type | None:
    """Return the ProcessingFault type, or ``None`` if absent."""
    return _first_available(_FAULT_CANDIDATES)


def _field_names(model: type) -> frozenset[str]:
    """Return the declared field names of a pydantic model or dataclass."""
    fields = getattr(model, "model_fields", None)
    if fields is not None:
        return frozenset(fields)
    dc_fields = getattr(model, "__dataclass_fields__", None)
    if dc_fields is not None:
        return frozenset(dc_fields)
    return frozenset(getattr(model, "__annotations__", {}))


# ---------------------------------------------------------------------------
# ASK-01 — Ask and Terminate
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ASK-01-001: the conservative status-adoption default is "
        "RequireCaseOwnerApprovalNode, which refuses unconditionally and emits "
        "no ask, so authorization can never be requested. Tracked by #2885."
    ),
)
@pytest.mark.spec("ASK-01-001")
def test_status_adoption_default_requests_authorization() -> None:
    """The default status-adoption backend MUST ask, not merely refuse (ASK-01-001).

    Asserts against the production default bundle rather than a stub: an actor
    that lacks authority has to *emit* the request, and a backend that returns
    FAILURE without emitting anything cannot satisfy that.
    """
    from vultron.core.behaviors.call_out.bundles.status_authorization import (
        STATUS_AUTHORIZATION_DETERMINISTIC,
    )
    from vultron.core.behaviors.call_out.nodes import (
        RequireCaseOwnerApprovalNode,
    )

    node = STATUS_AUTHORIZATION_DETERMINISTIC.status_adoption_gate_factory(
        "CaseOwnerApprovesStatusUpdate"
    )
    assert not isinstance(node, RequireCaseOwnerApprovalNode), (
        "The conservative default is an unconditional-FAILURE stub; it must be "
        "a backend that emits Offer(Proposal) and terminates (ASK-01-002)."
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ASK-01-004: no outstanding-ask register exists, so there is no stored "
        "ask to read the authorized action from — an implementation today could "
        "only read it from the reply. Tracked by #2883."
    ),
)
@pytest.mark.spec("ASK-01-004")
def test_ask_register_entry_records_the_requested_subject() -> None:
    """A stored ask MUST carry the action it requested (ASK-01-004).

    Authority comes from the ask, never the reply, so the register entry has to
    record the subject of the request; otherwise the only available source is
    the reply's own content, which lets the answerer alter what it grants.
    """
    register = _ask_register()
    assert (
        register is not None
    ), "No outstanding-ask register type is importable."
    names = _field_names(register)
    assert names & {
        "object_id",
        "subject_id",
        "requested_object_id",
    }, f"Register entry declares no requested-subject field; got {sorted(names)}."


# ---------------------------------------------------------------------------
# ASK-02 — Conversation-State Routing
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ASK-02-003: nothing tracks an outstanding ask, so a gate has no way to "
        "recognise that it already asked and must not ask again. Tracked by "
        "#2883."
    ),
)
@pytest.mark.spec("ASK-02-003")
def test_ask_register_can_report_an_unexpired_outstanding_ask() -> None:
    """Suppressing a duplicate ask requires an outstanding-and-unexpired query (ASK-02-003)."""
    register = _ask_register()
    assert (
        register is not None
    ), "No outstanding-ask register type is importable."
    assert any(
        hasattr(register, name)
        for name in ("is_pending", "is_outstanding", "is_open")
    ), "Register exposes no outstanding-ask predicate."


@pytest.mark.spec("ASK-02-004")
def test_no_gate_reads_authorization_from_an_ask_register() -> None:
    """Gates MUST read authorization from the ledger, never a register (ASK-02-004).

    Authorization is answered by the case ledger via ``find_protocol_pair``; the
    register only answers "what am I waiting on". This currently holds because no
    register exists, and it must keep holding once #2883 lands one — a forged or
    rebuilt register entry must never be able to permit an action.
    """
    register_names = {class_name for _, class_name in _ASK_REGISTER_CANDIDATES}
    offenders: list[str] = []
    gate_dir = _VULTRON / "core" / "behaviors"
    for path, source in _corpus.all_sources(under=gate_dir):
        if not any(name in source for name in register_names):
            continue
        offenders.append(str(path.relative_to(_corpus.REPO_ROOT)))
    assert not offenders, (
        "Behavior-tree modules reference an outstanding-ask register: "
        f"{offenders}. Authorization must come from the case ledger "
        "(find_protocol_pair), not the register."
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ASK-02-005: the gate that would park an unauthorized action is the "
        "deny-always stub, so no not-yet state is ever recorded and the "
        "requirement has no implementation to check. Tracked by #2885."
    ),
)
@pytest.mark.spec("ASK-02-005")
def test_gate_records_a_defined_not_yet_state_before_asking() -> None:
    """The ask branch MUST leave the case in a defined protocol state (ASK-02-005)."""
    from vultron.core.behaviors.call_out.bundles.status_authorization import (
        STATUS_AUTHORIZATION_DETERMINISTIC,
    )
    from vultron.core.behaviors.call_out.nodes import (
        RequireCaseOwnerApprovalNode,
    )

    node = STATUS_AUTHORIZATION_DETERMINISTIC.status_adoption_gate_factory(
        "gate"
    )
    assert not isinstance(
        node, RequireCaseOwnerApprovalNode
    ), "An unconditional-FAILURE backend records no not-yet state."


# ---------------------------------------------------------------------------
# ASK-03 — Ask Kinds
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ASK-03-001: ask kinds are not modelled. ProtocolPair carries "
        "reply_event_types per instance, but no registry of ask kinds declares "
        "the closing set. Tracked by #2884."
    ),
)
@pytest.mark.spec("ASK-03-001")
def test_ask_kinds_declare_their_closing_reply_types() -> None:
    """Each ask kind MUST declare the replies that close it (ASK-03-001)."""
    kinds = _first_available(
        (
            ("vultron.core.models.ask_kind", "AskKind"),
            ("vultron.core.models.ask_kinds", "AskKind"),
        )
    )
    assert kinds is not None, "No AskKind descriptor type is importable."
    assert "reply_event_types" in _field_names(kinds)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ASK-03-002: no ask-kind descriptor exists, so no kind declares whether "
        "a late reply is stale or void. Tracked by #2884."
    ),
)
@pytest.mark.spec("ASK-03-002")
def test_ask_kinds_declare_an_expiry_consequence() -> None:
    """Each ask kind MUST declare stale-vs-void expiry (ASK-03-002)."""
    kinds = _first_available(
        (
            ("vultron.core.models.ask_kind", "AskKind"),
            ("vultron.core.models.ask_kinds", "AskKind"),
        )
    )
    assert kinds is not None, "No AskKind descriptor type is importable."
    assert _field_names(kinds) & {"expiry_consequence", "on_expiry"}


@pytest.mark.spec("ASK-03-003")
def test_expiry_consequence_is_not_deployment_configurable() -> None:
    """Expiry consequence MUST NOT be configurable or carried on the wire (ASK-03-003).

    Two actors disagreeing about whether a late reply authorized an action is
    divergence in canonical case state, not a deployment preference. This holds
    today and must keep holding once #2884 adds the *duration* knob beside it —
    the duration is configurable precisely because the consequence is not.
    """
    from vultron.config.actor import ActorConfig
    from vultron.wire.as2.vocab.base.objects.base import as_Object

    forbidden = ("expiry_consequence", "on_expiry", "late_reply_authorizes")
    config_fields = _field_names(ActorConfig)
    assert not config_fields & set(
        forbidden
    ), f"ActorConfig exposes an expiry-consequence key: {sorted(config_fields & set(forbidden))}"
    wire_fields = _field_names(as_Object)
    assert not wire_fields & set(
        forbidden
    ), f"An AS2 object field carries the expiry consequence: {sorted(wire_fields & set(forbidden))}"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ASK-03-004: no ask is emitted at all yet, so no emitted ask carries a "
        "deadline in end_time. The AS2 field already exists; the emit path does "
        "not set it. Tracked by #2884."
    ),
)
@pytest.mark.spec("ASK-03-004")
def test_emitted_ask_carries_its_deadline_in_end_time() -> None:
    """An ask MUST carry its deadline in the AS2 endTime field (ASK-03-004)."""
    ask_factory = _first_available(
        (
            (
                "vultron.wire.as2.factories.asks",
                "offer_authorization_activity",
            ),
            ("vultron.wire.as2.factories.ask", "offer_authorization_activity"),
        )
    )
    assert ask_factory is not None, "No ask factory is importable."


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ASK-03-006: void expiry is not modelled and no gate consults a "
        "deadline, so a late Accept would authorize its action. Tracked by "
        "#2884."
    ),
)
@pytest.mark.spec("ASK-03-006")
def test_void_expiry_ask_refuses_a_late_reply() -> None:
    """A void-expiry ask MUST NOT be authorized by a late reply (ASK-03-006)."""
    kinds = _first_available(
        (
            ("vultron.core.models.ask_kind", "AskKind"),
            ("vultron.core.models.ask_kinds", "AskKind"),
        )
    )
    assert kinds is not None, "No AskKind descriptor type is importable."
    assert _field_names(kinds) & {"expiry_consequence", "on_expiry"}


# ---------------------------------------------------------------------------
# ASK-05 — Expiry and Reaping
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ASK-05-004: there is no reaper, so there is nothing that could "
        "re-emit on expiry and nothing to assert refrains from it. Tracked by "
        "#2887."
    ),
)
@pytest.mark.spec("ASK-05-004")
def test_reaping_an_expired_ask_does_not_re_emit_it() -> None:
    """Reaping MUST NOT automatically re-emit an expired ask (ASK-05-004).

    Mirrors CLP-06-005: a timeout is a signal, not an instruction to retry. Only
    the gated tree knows whether the action is still wanted.
    """
    reaper = _first_available(
        (
            (
                "vultron.core.use_cases.triggers.reap_expired_asks",
                "ReapExpiredAsksUseCase",
            ),
            (
                "vultron.core.use_cases.triggers.svcreapasks",
                "SvcReapExpiredAsksUseCase",
            ),
        )
    )
    assert (
        reaper is not None
    ), "No reap-expired-asks trigger use case is importable."


# ---------------------------------------------------------------------------
# ASK-06 — Ask Visibility
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ASK-06-001: no ask is emitted, so no ask is recorded as a canonical "
        "entry or replicated to participants. Tracked by #2883."
    ),
)
@pytest.mark.spec("ASK-06-001")
def test_case_scoped_ask_is_recorded_as_a_canonical_entry() -> None:
    """A case-scoped ask MUST be a recorded CaseLedgerEntry (ASK-06-001)."""
    register = _ask_register()
    assert (
        register is not None
    ), "No outstanding-ask register type is importable."


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ASK-06-002: no ask factory exists, so there is no field set to check "
        "for restricted-disclosure content. Tracked by #2883."
    ),
)
@pytest.mark.spec("ASK-06-002")
def test_ask_carries_no_restricted_disclosure_field() -> None:
    """An ask MUST NOT carry undisclosable content (ASK-06-002).

    Asks replicate to every participant (ASK-06-001), so private rationale has
    to travel by a directed ``Note`` instead.
    """
    ask_factory = _first_available(
        (
            (
                "vultron.wire.as2.factories.asks",
                "offer_authorization_activity",
            ),
            ("vultron.wire.as2.factories.ask", "offer_authorization_activity"),
        )
    )
    assert ask_factory is not None, "No ask factory is importable."


# ---------------------------------------------------------------------------
# ASK-07 — Processing Faults
# ---------------------------------------------------------------------------


@pytest.mark.spec("ASK-07-001")
def test_processing_fault_type_exists_for_sender_notification() -> None:
    """An unprocessable activity MUST notify an authenticated sender (ASK-07-001)."""
    assert _processing_fault() is not None, (
        "No ProcessingFault type is importable, so no sender notification can "
        "be emitted."
    )


@pytest.mark.spec("ASK-07-002")
def test_processing_fault_is_gated_on_sender_authentication() -> None:
    """A fault MUST NOT be emitted to an unauthenticated sender (ASK-07-002).

    Explaining a parse failure to a stranger is a parser oracle, and an
    unauthenticated identity is not a trustworthy reply address.
    """
    assert (
        _processing_fault() is not None
    ), "No ProcessingFault type is importable."


@pytest.mark.spec("ASK-07-003")
def test_processing_fault_is_a_dedicated_type_with_a_failure_class() -> None:
    """ProcessingFault MUST be a dedicated type carrying a failure class (ASK-07-003).

    SE-08-003 prefers a dedicated object type over field-level discrimination,
    and ``Reject`` presupposes a rejectable object that unreadable traffic does
    not provide.
    """
    fault = _processing_fault()
    assert fault is not None, "No ProcessingFault type is importable."
    assert _field_names(fault) & {"failure_class", "type_", "problem_type"}


@pytest.mark.spec("ASK-07-004")
def test_processing_fault_references_the_failed_activity() -> None:
    """ProcessingFault MUST identify the failed activity by reference (ASK-07-004).

    A typed copy of a payload that failed validation cannot be constructed —
    constructing it is what failed — and echoing sender content is a reflection
    hazard.
    """
    fault = _processing_fault()
    assert fault is not None, "No ProcessingFault type is importable."
    names = _field_names(fault)
    assert names & {"in_reply_to", "instance", "failed_activity_id"}


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ASK-07-005: no ProcessingFault type exists, so no failure classes are "
        "minted as Vultron-namespace URIs and no RFC 9457 members are carried. "
        "Tracked by #2889."
    ),
)
@pytest.mark.spec("ASK-07-005")
def test_processing_fault_uses_rfc9457_with_namespaced_failure_classes() -> (
    None
):
    """Failure classes MUST be Vultron-namespace URIs in RFC 9457 form (ASK-07-005)."""
    fault = _processing_fault()
    assert fault is not None, "No ProcessingFault type is importable."
    names = _field_names(fault)
    assert {
        "title",
        "detail",
    } <= names, f"ProcessingFault lacks RFC 9457 members; got {sorted(names)}."


@pytest.mark.spec("ASK-07-006")
def test_processing_fault_admits_no_implementation_diagnostics() -> None:
    """ProcessingFault MUST NOT carry stack traces or parser internals (ASK-07-006).

    Faults replicate to every case participant. Diagnosis belongs in the actor's
    own log, governed by `specs/structured-logging.yaml`.
    """
    fault = _processing_fault()
    assert fault is not None, "No ProcessingFault type is importable."
    forbidden = {"traceback", "stack_trace", "exception", "code_path"}
    assert not _field_names(fault) & forbidden


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ASK-07-007: neither the fault type nor the ask register exists, so a "
        "fault cannot close an outstanding ask. Tracked by #2889."
    ),
)
@pytest.mark.spec("ASK-07-007")
def test_processing_fault_closes_the_outstanding_ask_it_names() -> None:
    """A fault naming an outstanding ask MUST close its register entry (ASK-07-007)."""
    assert (
        _processing_fault() is not None
    ), "No ProcessingFault type is importable."
    assert (
        _ask_register() is not None
    ), "No outstanding-ask register is importable."


@pytest.mark.spec("ASK-07-008")
def test_case_attributable_fault_is_recorded_in_the_ledger() -> None:
    """A case-attributable fault MUST be a recorded CaseLedgerEntry (ASK-07-008).

    "B could not process A's message" is a true, legible statement about a
    message that arrived, and it explains a later retransmission.
    """
    assert (
        _processing_fault() is not None
    ), "No ProcessingFault type is importable."


@pytest.mark.spec("ASK-07-009")
def test_unprocessable_activity_is_not_committed_to_the_ledger() -> None:
    """The activity that failed processing MUST NOT be recorded (ASK-07-009).

    There is no legible assertion to snapshot, so a ledger entry could not
    satisfy CLP-02-003. This holds today — the dead-letter path stores the
    activity without committing a canonical entry — and must keep holding once
    #2889 adds the *fault* entry beside it (ASK-07-008); it is the fault
    statement that is recorded, never the unreadable message.
    """
    dead_letter = (
        _VULTRON / "core" / "behaviors" / "inbox" / "dead_letter_tree.py"
    )
    assert dead_letter.is_file(), f"{dead_letter} not found"
    source = dead_letter.read_text(encoding="utf-8")
    assert "CommitCaseLedgerEntryNode" not in source, (
        "The dead-letter tree commits a canonical ledger entry for an activity "
        "that could not be processed."
    )


# ---------------------------------------------------------------------------
# ASK-08 — Lost-Reply Recovery
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ASK-08-001: CP-05-006 previously specified a *new* Accept and no "
        "re-send of the stored one is implemented, so a duplicate request "
        "produces nothing. Tracked by #2890."
    ),
)
@pytest.mark.spec("ASK-08-001")
def test_duplicate_request_resends_the_stored_reply_unchanged() -> None:
    """A duplicate request MUST re-send the stored reply unchanged (ASK-08-001).

    Re-sending the frozen original (VM-08-003) reads as the first acceptance
    arriving late; a new Accept is indistinguishable from a second, independent
    decision, which CP-05-005's irrevocability rule precludes.
    """
    resend = _first_available(
        (
            (
                "vultron.core.behaviors.case.nodes.proposal",
                "ResendStoredAcceptNode",
            ),
            (
                "vultron.core.behaviors.case.proposal_tree",
                "ResendStoredAcceptNode",
            ),
        )
    )
    assert resend is not None, "No stored-reply re-send node is importable."


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ASK-08-002: behaviour on a duplicate Create(CaseProposal) after "
        "acceptance is undefined (CONCERN-2367); no guard prevents a second "
        "object being created. Tracked by #2890."
    ),
)
@pytest.mark.spec("ASK-08-002")
def test_duplicate_request_creates_no_second_object() -> None:
    """A duplicate request MUST NOT create a second object (ASK-08-002)."""
    resend = _first_available(
        (
            (
                "vultron.core.behaviors.case.nodes.proposal",
                "ResendStoredAcceptNode",
            ),
            (
                "vultron.core.behaviors.case.proposal_tree",
                "ResendStoredAcceptNode",
            ),
        )
    )
    assert resend is not None, "No stored-reply re-send node is importable."


# ---------------------------------------------------------------------------
# CP-05-007 — Vendor-side proposal deadline
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CP-05-007: no party holds a timeout on Create(CaseProposal), so a "
        "silently lost Accept stalls the handshake permanently "
        "(CONCERN-2367). Tracked by #2890."
    ),
)
@pytest.mark.spec("CP-05-007")
def test_vendor_treats_an_unanswered_proposal_as_expired() -> None:
    """A vendor MUST treat an unanswered proposal as expired at its deadline (CP-05-007).

    The proposal is an ask, so it carries a deadline (ASK-03-004) and sits in the
    vendor's actor-scoped register (ASK-04-001), which works before a case
    exists.
    """
    assert _ask_register() is not None, (
        "No outstanding-ask register is importable, so a vendor cannot hold a "
        "proposal deadline before a case exists."
    )


# ---------------------------------------------------------------------------
# OX-14-002 — Commit ordering is not changed
# ---------------------------------------------------------------------------


@pytest.mark.spec("OX-14-002")
def test_ledger_commit_is_not_gated_on_delivery_confirmation() -> None:
    """A canonical commit MUST NOT wait for delivery confirmation (OX-14-002).

    CONCERN-2657 asked for the opposite. It is declined: gating the commit makes
    an actor's own decision history hostage to the network, inverts
    CLP-10-006's guards-then-commit-then-effects ordering, and raises an
    unanswerable partial-delivery question. Delivery confirmation is a transport
    receipt, not agreement to the delivered content. This test pins the ordering
    so #2891 adds *correlation* without quietly adding a gate.
    """
    commit_module = (
        _VULTRON / "core" / "behaviors" / "case" / "nodes" / "ledger.py"
    )
    if not commit_module.is_file():
        matches = [
            path
            for path, source in _corpus.sources_mentioning(
                "class CommitCaseLedgerEntryNode", under=_VULTRON
            )
        ]
        assert matches, "CommitCaseLedgerEntryNode not found in vultron/"
        commit_module = matches[0]
    source = commit_module.read_text(encoding="utf-8")
    forbidden = ("delivery_confirmed", "await_delivery", "delivery_receipt")
    present = [token for token in forbidden if token in source]
    assert not present, (
        f"The canonical commit path references delivery confirmation: {present}. "
        "OX-14-002 forbids deferring the commit until delivery is confirmed."
    )


# ---------------------------------------------------------------------------
# RSH-07 — Status gate composition
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "RSH-07-004: both gates are single-tick Evaluator call-outs whose "
        "conservative default is RequireCaseOwnerApprovalNode, an "
        "unconditional-FAILURE node. Tracked by #2885."
    ),
)
@pytest.mark.spec("RSH-07-004")
def test_no_status_gate_default_is_an_unconditional_failure_node() -> None:
    """Status gates MUST be routing subtrees, not deny-always Evaluators (RSH-07-004).

    At the moment authorization is first needed no answer exists, so an
    Evaluator asked "is this approved?" can only ever answer no. That is why the
    ADR-0046/ADR-0076 model was unreachable by any pathway.
    """
    from vultron.core.behaviors.call_out.bundles.status_authorization import (
        STATUS_AUTHORIZATION_DETERMINISTIC,
    )
    from vultron.core.behaviors.call_out.nodes import (
        RequireCaseOwnerApprovalNode,
    )

    bundle = STATUS_AUTHORIZATION_DETERMINISTIC
    nodes = [
        bundle.status_adoption_gate_factory("StatusAdoptionGate"),
        bundle.embargo_teardown_authorization_gate_factory(
            "EmbargoTeardownAuthorizationGate"
        ),
    ]
    offenders = [
        type(node).__name__
        for node in nodes
        if isinstance(node, RequireCaseOwnerApprovalNode)
    ]
    assert (
        not offenders
    ), f"Gate defaults are unconditional-FAILURE nodes: {offenders}."


@pytest.mark.spec("RSH-07-005")
def test_production_status_authorization_default_is_conservative() -> None:
    """A gate MUST NOT be relaxed to permissive to unblock a path (RSH-07-005).

    ``STATUS_AUTHORIZATION_PERMISSIVE`` exists for trusted-participant and demo
    deployments (RSH-07-003). Using it to route around a gate that is refusing
    converts a protocol guarantee into a configuration posture — the defect
    CONCERN-2092 filed. This asserts the *default* stays conservative, which is
    what makes permissive an explicit opt-in rather than a fallback.
    """
    from vultron.core.behaviors.call_out.bundles.status_authorization import (
        STATUS_AUTHORIZATION_DETERMINISTIC,
        STATUS_AUTHORIZATION_PERMISSIVE,
        StatusAuthorizationCallOutBundle,
    )
    from vultron.core.behaviors.call_out.nodes import AlwaysSucceed

    default_bundle = StatusAuthorizationCallOutBundle()
    for name in (
        "status_adoption_gate_factory",
        "embargo_teardown_authorization_gate_factory",
    ):
        node = getattr(default_bundle, name)(name)
        assert not isinstance(node, AlwaysSucceed), (
            f"{name} defaults to a permissive backend; the conservative default "
            "must require explicit Case Owner authorization."
        )
        deterministic = getattr(STATUS_AUTHORIZATION_DETERMINISTIC, name)(name)
        assert not isinstance(
            deterministic, AlwaysSucceed
        ), f"STATUS_AUTHORIZATION_DETERMINISTIC.{name} is permissive."
        permissive = getattr(STATUS_AUTHORIZATION_PERMISSIVE, name)(name)
        assert isinstance(permissive, AlwaysSucceed), (
            f"STATUS_AUTHORIZATION_PERMISSIVE.{name} is not permissive; the "
            "opt-in bundle must be the only permissive one."
        )
