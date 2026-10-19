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

"""The replica embargo slots run no lifecycle logic (#4294 AC-3, CM-23-016).

A replica writes the embargo register and consent rows by copying the
CASE_MANAGER's entries through the one apply function (ADR-0124), never by
re-running ``EmbargoLifecycle`` or a consent transition on its own state.
Every slot of ``AnnounceLogEntryReceivedBT`` that writes either is covered:
relay, activation, the owner's rejection, abandonment, expiry, teardown,
withdrawal, the consent-row copy, and the stub Invite answers that carry a
joiner's consent (:data:`_SLOTS`), and
:func:`test_every_replica_embargo_slot_is_checked` keeps that list whole.

The check is per class, over every class in each slot's MRO that this
codebase defines, because ``abandon.py`` and ``withdrawal.py`` also hold the
CASE_MANAGER's own nodes, which decide through ``EmbargoLifecycle`` as they
must.  It also follows every module-level function and core model method a
slot reaches, however indirectly, so a slot cannot hand the work to a helper
or a model method that runs it.

The one tracked deviation is the owner's-rejection slot's skip of a
``Reject`` the CASE_MANAGER answered with ET (#4789): it reads one shared
predicate rather than copying, and
:func:`test_only_the_owner_rejection_slot_decides_a_skip` keeps it the only
one.  The CM-31-010 notice path (``ending_notice_replica.py``) applies no
ledger entry and is outside CM-23-016's scope.
"""

import ast
import functools
import importlib
import inspect
import pkgutil
import sys
import textwrap
import types
from collections.abc import Iterable
from typing import Any, cast

import pytest

import vultron.core.behaviors.embargo.nodes as embargo_nodes
import vultron.core.behaviors.sync.nodes as sync_nodes
import vultron.core.models as core_models
from test.architecture import _corpus
from vultron.core.behaviors.embargo.nodes.abandon import (
    ApplyEmbargoAbandonmentFromLedgerNode,
)
from vultron.core.behaviors.embargo.nodes.activation_effect import (
    ApplyEmbargoActivationFromLedgerNode,
    ApplyEmbargoProposalRejectionFromLedgerNode,
)
from vultron.core.behaviors.embargo.nodes.expiry import (
    ApplyHonourLateAcceptFromLedgerNode,
    ApplyInviteExpiryFromLedgerNode,
    ApplyInviteExpiryNoopFromLedgerNode,
)
from vultron.core.behaviors.embargo.nodes.relay_effect import (
    ApplyEmbargoAcceptanceFromLedgerNode,
    ApplyEmbargoInviteFromLedgerNode,
    ApplyEmbargoProposalFromLedgerNode,
    ApplyEmbargoReinviteFromLedgerNode,
    ApplyEmbargoRejectionFromLedgerNode,
)
from vultron.core.behaviors.embargo.nodes.teardown import (
    ApplyEmbargoTeardownNode,
)
from vultron.core.behaviors.embargo.nodes.withdrawal import (
    ApplyEmbargoWithdrawalFromLedgerNode,
)
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.behaviors.sync.nodes.embargo_copy_effect import (
    ApplyEmbargoChangeFromLedgerNode,
    ApplyEmbargoConsentFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.participant_record_effect import (
    ApplyCreateCaseParticipantFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.stub_reply_effect import (
    ApplyInviteAcceptFromLedgerNode,
    ApplyInviteRejectFromLedgerNode,
)
from vultron.core.use_cases.received.sync import (
    AnnounceLedgerEntryReceivedUseCase,
)

#: Names a copying slot must never reach for (CM-23-016, CM-18-005).
#: ``TransitionMode`` catches a slot that passes a lifecycle mode on; a
#: slot that hands off to a lifecycle-running node is caught by
#: :func:`_lifecycle_nodes`, as the owner's-rejection slot did before #4784.
_LIFECYCLE_NAMES = frozenset(
    {
        "EmbargoLifecycle",
        "TransitionMode",
        "apply_pec_transition",
        "apply_pec_transition_if_legal",
        "accepts_pec_trigger",
        "write_uninvited_rows",
    }
)

#: Every replica slot that writes the embargo register or a consent row.
_SLOTS = [
    # relay (EP-09-007)
    ApplyEmbargoProposalFromLedgerNode,
    ApplyEmbargoInviteFromLedgerNode,
    ApplyEmbargoReinviteFromLedgerNode,
    ApplyEmbargoAcceptanceFromLedgerNode,
    ApplyEmbargoRejectionFromLedgerNode,
    # the owner's activation and rejection (ADR-0122)
    ApplyEmbargoActivationFromLedgerNode,
    ApplyEmbargoProposalRejectionFromLedgerNode,
    # abandonment (EMB-16-001)
    ApplyEmbargoAbandonmentFromLedgerNode,
    # expiry and late Accepts (CM-28-014, EMB-17)
    ApplyInviteExpiryFromLedgerNode,
    ApplyInviteExpiryNoopFromLedgerNode,
    ApplyHonourLateAcceptFromLedgerNode,
    # teardown (EP-08-004)
    ApplyEmbargoTeardownNode,
    # withdrawal (MSM-07-010)
    ApplyEmbargoWithdrawalFromLedgerNode,
    # the CASE_MANAGER's own consent-row entries (ADR-0124)
    ApplyEmbargoConsentFromLedgerNode,
    # the stub Invite answers, which carry a joiner's consent (CM-11-016)
    ApplyInviteAcceptFromLedgerNode,
    ApplyInviteRejectFromLedgerNode,
    # the roster entry, which seats a record carried with all its rows
    ApplyCreateCaseParticipantFromLedgerNode,
]

#: Names whose use marks a slot as writing the register or a consent row:
#: the one apply function and the model writes behind it, and every
#: lifecycle name.  A slot of the announce tree that reaches one must be in
#: :data:`_SLOTS`.
_WRITER_NAMES = _LIFECYCLE_NAMES | {
    "apply_embargo_change",
    "apply_embargo_register_step",
    "copy_consent_row",
    "embargo_consents",
    "embargo_register",
    "add_participant",
}


def _names_used(obj: object) -> set[str]:
    """Every bare name and attribute name *obj*'s source uses."""
    source = inspect.getsource(cast(Any, obj))
    tree = _corpus.parse_inline(textwrap.dedent(source))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _own_classes(slot: type) -> list[type]:
    return [c for c in slot.__mro__ if c.__module__.startswith("vultron.")]


def _uses_lifecycle(cls: type) -> bool:
    used = set().union(*(_names_used(c) for c in _own_classes(cls)))
    return bool(used & _LIFECYCLE_NAMES)


#: The core model writes behind the one apply function, deliberately not
#: followed (see :func:`_functions_reached`).
_UNWALKED_MODEL_WRITES = frozenset(
    {
        "VulnerabilityCase.apply_embargo_register_step",
        "VulnerabilityCase.add_participant",
    }
)


def _function_of(attr: object) -> types.FunctionType | None:
    """The function a class attribute runs, unwrapping a descriptor."""
    if isinstance(attr, (staticmethod, classmethod)):
        attr = attr.__func__
    elif isinstance(attr, property):
        attr = attr.fget
    return attr if isinstance(attr, types.FunctionType) else None


@functools.cache
def _model_methods() -> dict[str, tuple[types.FunctionType, ...]]:
    """Every method a ``vultron.core.models`` class defines, by name.

    Static and class methods and property getters count too.  A call is
    matched to every method of its name, whatever the receiver, so a name
    two models share follows both: the walk over-follows rather than misses.
    """
    methods: dict[str, list[types.FunctionType]] = {}
    for info in pkgutil.walk_packages(
        core_models.__path__, f"{core_models.__name__}."
    ):
        module = importlib.import_module(info.name)
        for cls in vars(module).values():
            if not inspect.isclass(cls) or cls.__module__ != module.__name__:
                continue
            for name, attr in vars(cls).items():
                function = _function_of(attr)
                if (
                    function is not None
                    # Methods compiled elsewhere (dataclass- or
                    # pydantic-generated dunders) have no source here to walk.
                    and function.__code__.co_filename == module.__file__
                    and function.__qualname__ not in _UNWALKED_MODEL_WRITES
                ):
                    methods.setdefault(name, []).append(function)
    return {name: tuple(found) for name, found in methods.items()}


def _functions_reached(
    cls: type, *, follow_methods: bool = True
) -> dict[str, set[str]]:
    """Each codebase function *cls* reaches, and the names it uses.

    Starts from every class in *cls*'s MRO that this codebase defines.
    """
    return _reach(_own_classes(cls), follow_methods=follow_methods)


def _reach(
    roots: Iterable[object], *, follow_methods: bool = True
) -> dict[str, set[str]]:
    """Each codebase function *roots* reach by name, and the names it uses.

    Follows every name a class body or function body uses that resolves, in
    its module, to a module-level function this codebase defines, and every
    attribute name that a core model method bears
    (:func:`_model_methods`, unless *follow_methods* is false), and so on
    from there.  So a slot calling
    ``record.sign_embargo(...)`` reaches the PEC transition inside it.
    Classes are not followed: a slot's own classes are walked by MRO, and a
    lifecycle-running node class is forbidden by name.

    Blind spots, by construction: a function reached as ``module.func`` (an
    attribute that names no model method is not resolved); a method of a
    class outside ``vultron.core.models``, or of a class nested inside
    another; a ``functools.cached_property`` (not unwrapped by
    :func:`_function_of`); and a lifecycle-running node class outside
    ``embargo/nodes`` (:func:`_lifecycle_nodes`).  None of the nested or
    cached kinds exists in ``vultron.core.models`` today.

    Two model writes behind the one apply function stay unwalked, on
    purpose (:data:`_UNWALKED_MODEL_WRITES`):
    ``VulnerabilityCase.apply_embargo_register_step`` gives an *inline*
    participant its ``UNINVITED`` rows so the register assignment validates,
    and ``VulnerabilityCase.add_participant`` gives a seated record a row
    for each register entry it lacks.  A carried record already holds every
    row, so on a replica neither writes one; the rebuild-from-ledger check
    (``test/support/ledger_rebuild.py``) compares every record whole and
    would fail if one did.
    """
    reached: dict[str, set[str]] = {}
    pending: list[object] = list(roots)
    seen: set[int] = set()
    while pending:
        obj = pending.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        names = _names_used(obj)
        if isinstance(obj, types.FunctionType):
            reached[f"{obj.__module__}.{obj.__qualname__}"] = names
        module_globals = vars(sys.modules[cast(Any, obj).__module__])
        for name in names:
            value = module_globals.get(name)
            if isinstance(
                value, types.FunctionType
            ) and value.__module__.startswith("vultron."):
                pending.append(value)
            if follow_methods:
                pending.extend(_model_methods().get(name, ()))
    return reached


@functools.cache
def _lifecycle_nodes() -> frozenset[str]:
    """Every embargo node class that itself runs lifecycle logic.

    Delegating to one of them is running lifecycle logic too, whatever mode
    it is given.
    """
    names: set[str] = set()
    for info in pkgutil.iter_modules(embargo_nodes.__path__):
        module = importlib.import_module(
            f"{embargo_nodes.__name__}.{info.name}"
        )
        for name, value in vars(module).items():
            if (
                inspect.isclass(value)
                and value.__module__ == module.__name__
                and _uses_lifecycle(value)
            ):
                names.add(name)
    return frozenset(names)


@pytest.mark.spec("CM-23-016")
@pytest.mark.spec("EP-09-007")
@pytest.mark.parametrize("slot", _SLOTS, ids=lambda c: c.__name__)
def test_a_copying_replica_slot_runs_no_lifecycle_logic(slot: type) -> None:
    forbidden = _LIFECYCLE_NAMES | _lifecycle_nodes()
    used = set().union(*(_names_used(c) for c in _own_classes(slot)))
    assert not used & forbidden, (
        f"{slot.__name__} reaches {sorted(used & forbidden)}"
    )


@pytest.mark.spec("CM-23-016")
@pytest.mark.parametrize("slot", _SLOTS, ids=lambda c: c.__name__)
def test_no_function_a_slot_reaches_runs_lifecycle_logic(slot: type) -> None:
    """A slot cannot run the lifecycle through a helper it calls."""
    forbidden = _LIFECYCLE_NAMES | _lifecycle_nodes()
    offenders = {
        function: sorted(names & forbidden)
        for function, names in _functions_reached(slot).items()
        if names & forbidden
    }
    assert not offenders, f"{slot.__name__} reaches {offenders}"


def test_the_walk_follows_a_slots_helpers() -> None:
    """The walk is not vacuous: it reaches the one apply function."""
    reached = _functions_reached(ApplyEmbargoConsentFromLedgerNode)

    assert "vultron.core.models.embargo_apply.apply_embargo_change" in reached


def test_the_walk_follows_a_model_method() -> None:
    """A PEC transition behind a model method is caught where it runs."""

    class _SignsOnReplica:
        def update(self, record: Any) -> None:
            record.sign_embargo("https://example.org/embargoes/1")

    offenders = {
        function
        for function, names in _reach([_SignsOnReplica]).items()
        if names & _LIFECYCLE_NAMES
    }

    assert any(f.endswith("CaseParticipant.sign_embargo") for f in offenders)


def _tree_slot_classes() -> set[type]:
    """Every apply node class ``AnnounceLogEntryReceivedBT`` runs."""
    return {
        type(node)
        for node in create_announce_log_entry_tree(
            sender_rule=AnnounceLedgerEntryReceivedUseCase.sender_entitlement
        ).iterate()
        if type(node).__name__.startswith("Apply")
    }


def _writes_embargo_state(cls: type) -> bool:
    """A slot that writes embargo state, by what it reaches or where it lives.

    It reaches a writer name through its own functions, reaches a lifecycle
    name through any model method, copies through the frame, or lives with
    the embargo nodes (the store-only relay slots, which write the embargo
    record itself).  A model method counts only for a lifecycle name: many
    of them merely read ``embargo_register`` (``VulnerabilityCase.em_state``).
    """
    names = set().union(*(_names_used(c) for c in _own_classes(cls)))
    for reached in _functions_reached(cls, follow_methods=False).values():
        names |= reached
    through_methods = set().union(*_functions_reached(cls).values())
    return bool(
        names & _WRITER_NAMES
        or through_methods & _LIFECYCLE_NAMES
        or issubclass(cls, ApplyEmbargoChangeFromLedgerNode)
        or cls.__module__.startswith(f"{embargo_nodes.__name__}.")
    )


@pytest.mark.spec("CM-23-016")
def test_every_replica_embargo_slot_is_checked() -> None:
    """A new embargo slot in the announce tree joins the ratchet."""
    embargo_slots = {
        c for c in _tree_slot_classes() if _writes_embargo_state(c)
    }

    assert embargo_slots, "the announce tree runs no embargo slot"
    missing = sorted(c.__name__ for c in embargo_slots - set(_SLOTS))
    assert not missing, f"add {missing} to _SLOTS"
    absent = sorted(c.__name__ for c in set(_SLOTS) - _tree_slot_classes())
    assert not absent, f"{absent} no longer run in the announce tree"


def test_the_check_sees_a_lifecycle_node() -> None:
    """Handing off to a lifecycle-running node is caught, with no mode."""
    assert {
        "DecideRejectedEmbargoProposalNode",
        "RejectEmbargoProposalLifecycleNode",
        "_EmbargoLifecycleNode",
    } <= _lifecycle_nodes()
    assert not _lifecycle_nodes() & {c.__name__ for c in _SLOTS}


def test_the_check_sees_a_lifecycle_call() -> None:
    """The detector is not vacuous: it finds a call where one is."""

    class _Replays:
        def update(self) -> None:
            EmbargoLifecycle(persistence=None).propose_embargo()  # type: ignore[name-defined]  # noqa: F821

    assert "EmbargoLifecycle" in _names_used(_Replays)


def _subclasses(cls: type) -> set[type]:
    found: set[type] = set()
    direct: list[type] = cls.__subclasses__()
    for sub in direct:
        found |= {sub} | _subclasses(sub)
    return found


def _slots_overriding(attr: str) -> set[str]:
    """Every copying-frame subclass that defines *attr* itself."""
    for package in (embargo_nodes, sync_nodes):
        for info in pkgutil.iter_modules(package.__path__):
            importlib.import_module(f"{package.__name__}.{info.name}")
    return {
        sub.__name__
        for sub in _subclasses(ApplyEmbargoChangeFromLedgerNode)
        if attr in vars(sub) and sub.__module__.startswith("vultron.")
    }


@pytest.mark.spec("CM-23-016")
def test_only_the_owner_rejection_slot_decides_a_skip() -> None:
    """The one tracked deviation from copy-only stays contained (#4789).

    ``_left_to_a_later_entry`` lets a slot decide, on the replica, that an
    entry changes nothing.  Only the owner's-rejection slot may, for the
    ``Reject`` the CASE_MANAGER answered with ET (EMB-04-002); a new
    override is a new deviation and needs its own decision.
    """
    assert _slots_overriding("_left_to_a_later_entry") == {
        ApplyEmbargoProposalRejectionFromLedgerNode.__name__
    }
