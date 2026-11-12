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
"""Every bundle field's default writes its capability's outputs (BT-23-013).

The capability a bundle field answers is read from the bindings, never a
hand-kept list: a field answers declaration *D* when the backend it builds
in any bundle singleton binds to *D* (``declaration()``).  The simulation
node of every declaration binds to it (``test_capability_declarations.py``),
so a field whose STOCHASTIC node answers a capability names it here.

- **DETERMINISTIC** (AC-3): every :class:`CallOutBundle` subclass's default
  instance is resolved field by field through the seam
  (:func:`unwrap_call_out`).  A field that answers a declaration has a
  default bound to that declaration, and a default that answers *yes* writes
  every declared output port with a value of its type (BT-18-002,
  BT-23-013).
- **STOCHASTIC** (AC-4): every ``*_STOCHASTIC`` singleton's field that
  answers a declaration builds a node bound to it, and that node, answering
  *yes*, writes every declared output port (BT-18-003).

A field is keyed by the most basic bundle class that declares it, so an
inherited field (``DeploymentMonitoringBundle``'s) is one field, checked
against every subclass singleton that builds it; every field that answers a
declaration has a simulation node, and its default keeps the STOCHASTIC
rate's yes/no direction (BT-23-002), save the pinned
:data:`DIRECTION_EXEMPTIONS`.

A field no singleton binds answers no declaration, so its backends are
binary and BT-23-013 does not reach it.  Those fields are the pinned
exemption set :data:`BINARY_FIELD_EXEMPTIONS`, kept equal to what the
bindings derive, and every backend they build declares no outputs.
"""

from __future__ import annotations

import dataclasses
import importlib
import pkgutil
from collections.abc import Iterator

import py_trees
import pytest
from py_trees.common import Status

import vultron.demo.fuzzer.bundles as stochastic_bundles
from test.support.call_out import bind_test_target
from vultron.core.behaviors.call_out import (
    bundles as core_bundles,
    unwrap_call_out,
)
from vultron.core.behaviors.call_out.bundles.base import CallOutBundle
from vultron.core.behaviors.call_out.capability import Capability
from vultron.core.behaviors.call_out.guard import SynchronousCallOut

FieldKey = tuple[str, str]


def _modules(package: object) -> Iterator[object]:
    for info in pkgutil.iter_modules(package.__path__):  # type: ignore[attr-defined]
        yield importlib.import_module(f"{package.__name__}.{info.name}")  # type: ignore[attr-defined]


def _bundle_classes() -> list[type[CallOutBundle]]:
    """Every core bundle class, by walking the bundles package."""
    found: dict[str, type[CallOutBundle]] = {}
    for module in _modules(core_bundles):
        for obj in vars(module).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, CallOutBundle)
                and obj is not CallOutBundle
                and dataclasses.is_dataclass(obj)
            ):
                found[obj.__qualname__] = obj
    return [found[name] for name in sorted(found)]


def _singletons(package: object, suffix: str) -> dict[str, CallOutBundle]:
    """Every bundle instance named ``*<suffix>`` in *package*'s modules."""
    found: dict[str, CallOutBundle] = {}
    for module in _modules(package):
        for name, obj in vars(module).items():
            if name.endswith(suffix) and isinstance(obj, CallOutBundle):
                found[name] = obj
    return found


_BUNDLE_CLASSES = _bundle_classes()
_DEFAULTS = {cls.__qualname__: cls() for cls in _BUNDLE_CLASSES}
_STOCHASTIC = _singletons(stochastic_bundles, "_STOCHASTIC")
_ALL_INSTANCES: list[CallOutBundle] = [
    *_DEFAULTS.values(),
    *_singletons(core_bundles, "_DETERMINISTIC").values(),
    *_singletons(core_bundles, "_PERMISSIVE").values(),
    *_STOCHASTIC.values(),
]


def _backend(
    bundle: CallOutBundle, field: str
) -> py_trees.behaviour.Behaviour:
    """The backend *field* builds, resolved through the seam."""
    node = getattr(bundle, field)(field)
    assert isinstance(node, SynchronousCallOut), (
        f"{type(bundle).__qualname__}.{field} is not behind the seam"
    )
    return unwrap_call_out(node)


def _key(bundle: CallOutBundle, field: str) -> FieldKey:
    """*field*'s key: the most basic bundle class that declares it.

    An inherited field is one field, so a shared base's fields
    (``DeploymentMonitoringBundle``) are checked against the singletons of
    every subclass that builds them.
    """
    owner = next(
        cls
        for cls in reversed(type(bundle).__mro__)
        if field in vars(cls).get("__annotations__", {})
    )
    return owner.__qualname__, field


def _declaration_of(node: py_trees.behaviour.Behaviour) -> type | None:
    if isinstance(node, Capability):
        return type(node).declaration()
    return None


def _field_declarations() -> dict[FieldKey, set[type]]:
    """Each bundle field's declarations, as every singleton binds them."""
    bound: dict[FieldKey, set[type]] = {}
    for bundle in _ALL_INSTANCES:
        for f in dataclasses.fields(bundle):  # type: ignore[arg-type]
            key = _key(bundle, f.name)
            declaration = _declaration_of(_backend(bundle, f.name))
            entry = bound.setdefault(key, set())
            if declaration is not None:
                entry.add(declaration)
    return bound


_FIELD_DECLARATIONS = _field_declarations()


def _answers(key: FieldKey) -> type[Capability] | None:
    declarations = _FIELD_DECLARATIONS[key]
    assert len(declarations) <= 1, (
        f"{key} binds to {sorted(d.__name__ for d in declarations)}; a "
        "field answers one capability (BT-18-021)"
    )
    return next(iter(declarations), None)


def _default_fields() -> list[FieldKey]:
    """Every default field that answers a capability.

    Read without :func:`_answers`, so a field bound to two capabilities
    fails its own test below instead of the module's collection.
    """
    return [
        (name, f.name)
        for name, bundle in _DEFAULTS.items()
        for f in dataclasses.fields(bundle)  # type: ignore[arg-type]
        if _FIELD_DECLARATIONS[_key(bundle, f.name)]
    ]


def _stochastic_fields() -> list[tuple[str, str]]:
    """Every STOCHASTIC singleton field that answers a capability."""
    return [
        (name, f.name)
        for name, bundle in sorted(_STOCHASTIC.items())
        for f in dataclasses.fields(bundle)  # type: ignore[arg-type]
        if _FIELD_DECLARATIONS[_key(bundle, f.name)]
    ]


def _id(key: tuple[str, str]) -> str:
    return ".".join(key)


def _tick_and_read(
    bundle: CallOutBundle, field: str
) -> tuple[Status, dict[str, object]]:
    """Tick *field*'s node behind the seam; return its status and writes."""
    py_trees.blackboard.Blackboard.storage.clear()
    node = bind_test_target(getattr(bundle, field)(field))
    node.tick_once()
    written = dict(py_trees.blackboard.Blackboard.storage)
    py_trees.blackboard.Blackboard.storage.clear()
    return node.status, written


def _missing_outputs(
    declaration: type[Capability], written: dict[str, object]
) -> list[str]:
    return sorted(
        key
        for key, port in declaration.OUTPUT_PORTS.items()
        if not isinstance(written.get(f"/{key}"), port.data_type)
    )


def test_the_bundles_and_singletons_are_found() -> None:
    assert len(_BUNDLE_CLASSES) > 10
    assert len(_STOCHASTIC) > 10
    assert any(
        (declaration := _answers(key)) is not None and declaration.OUTPUT_PORTS
        for key in _default_fields()
    ), "no field answers a capability that declares outputs"


@pytest.mark.spec("BT-18-021")
@pytest.mark.parametrize("key", sorted(_FIELD_DECLARATIONS), ids=_id)
def test_a_field_answers_at_most_one_capability(key: FieldKey) -> None:
    _answers(key)


@pytest.mark.spec("BT-18-002")
@pytest.mark.spec("BT-23-013")
@pytest.mark.parametrize("key", _default_fields(), ids=_id)
def test_deterministic_default_writes_every_declared_output(
    key: FieldKey,
) -> None:
    """The default binds to the field's capability and a yes writes its ports."""
    bundle_name, field = key
    bundle = _DEFAULTS[bundle_name]
    declaration = _answers(_key(bundle, field))
    assert declaration is not None
    default = _backend(bundle, field)
    assert _declaration_of(default) is declaration, (
        f"{_id(key)} answers {declaration.__name__} but its default "
        f"{type(default).__name__} binds to "
        f"{getattr(_declaration_of(default), '__name__', None)}; bind it with "
        "always_succeed_as() or always_fail_as() (BT-23-013)"
    )
    status, written = _tick_and_read(bundle, field)
    if status == Status.SUCCESS:
        assert not _missing_outputs(declaration, written), (
            f"{_id(key)} answered yes without "
            f"{_missing_outputs(declaration, written)} (BT-23-013)"
        )
    else:
        # Only a floor default answers no; a ceiling that declines would
        # skip the output check above (BT-23-002, BT-23-006).
        assert default.success_rate == 0.0, (  # type: ignore[attr-defined]
            f"{_id(key)} answered no from a ceiling default"
        )


@pytest.mark.spec("BT-18-003")
@pytest.mark.spec("BT-23-013")
@pytest.mark.parametrize("key", _stochastic_fields(), ids=_id)
def test_stochastic_node_writes_every_declared_output(
    key: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Answering yes, the field's simulation node writes the declared ports."""
    from vultron.demo.fuzzer import base

    singleton_name, field = key
    bundle = _STOCHASTIC[singleton_name]
    declaration = _answers(_key(bundle, field))
    assert declaration is not None
    node = _backend(bundle, field)
    assert _declaration_of(node) is declaration
    # The roll is patched to 0.0, so a probabilistic node takes its yes
    # branch through its real answer(); a constant floor never answers yes.
    monkeypatch.setattr(base.random, "random", lambda: 0.0)
    status, written = _tick_and_read(bundle, field)
    if status == Status.SUCCESS:
        assert not _missing_outputs(declaration, written), (
            f"{_id(key)} answered yes without "
            f"{_missing_outputs(declaration, written)} (BT-18-003)"
        )
    else:
        assert node.success_rate == 0.0, (  # type: ignore[attr-defined]
            f"{_id(key)} answered no with its roll patched to yes"
        )


# Pinned exemption set, not a ratchet: the bundle fields that answer no
# declared capability by design.  Each is a pass/fail gate whose verdict is
# the whole answer, so BT-23-013 does not reach it.  A new field missing from
# both sides' bindings fails the equality below instead of passing as binary
# (ARCH-18-001, ARCH-18-005).
# permanent: RSH-07-001 (the status adoption gate is a yes/no gate)
BINARY_FIELD_EXEMPTIONS: frozenset[FieldKey] = frozenset(
    {("StatusAuthorizationCallOutBundle", "status_adoption_gate_factory")}
)

_FIELDS_WITH_NO_CAPABILITY = BINARY_FIELD_EXEMPTIONS


@pytest.mark.spec("BT-23-013")
def test_the_fields_with_no_capability_are_exactly_the_pinned_set() -> None:
    unbound = {k for k in _FIELD_DECLARATIONS if _answers(k) is None}
    assert unbound == _FIELDS_WITH_NO_CAPABILITY, (
        "a field binds no capability on either side; bind its default and "
        "its simulation node to its declaration, or record here why it is "
        "binary (and drop a newly bound field from its exemption set)"
    )


@pytest.mark.spec("BT-23-013")
@pytest.mark.parametrize("key", sorted(_FIELDS_WITH_NO_CAPABILITY), ids=_id)
def test_a_field_with_no_capability_is_binary(key: FieldKey) -> None:
    """A field no singleton binds declares no outputs anywhere it is built.

    BT-23-013 reaches only a capability that declares output ports, so such
    a field (the status adoption gate) stays binary.
    """
    _, field = key
    for bundle in _ALL_INSTANCES:
        names = {f.name for f in dataclasses.fields(bundle)}  # type: ignore[arg-type]
        if field in names and _key(bundle, field) == key:
            backend = _backend(bundle, field)
            assert not backend.contract.outputs, (  # type: ignore[attr-defined]
                f"{_id(key)} builds {type(backend).__name__}, which declares "
                "outputs but binds no capability"
            )


def _stochastic_rates() -> dict[FieldKey, set[float]]:
    """Each field's STOCHASTIC success rates, over every singleton."""
    rates: dict[FieldKey, set[float]] = {}
    for bundle in _STOCHASTIC.values():
        for f in dataclasses.fields(bundle):  # type: ignore[arg-type]
            node = _backend(bundle, f.name)
            rates.setdefault(_key(bundle, f.name), set()).add(
                node.success_rate  # type: ignore[attr-defined]
            )
    return rates


_STOCHASTIC_RATES = _stochastic_rates()


@pytest.mark.spec("BT-23-013")
def test_the_direction_exemptions_are_real_fields() -> None:
    assert set(_FIELD_DECLARATIONS) >= DIRECTION_EXEMPTIONS


@pytest.mark.spec("BT-23-013")
def test_every_field_that_answers_a_capability_is_simulated() -> None:
    """The capability a field answers is cross-checked by a simulation node.

    Without one, the field's capability is read from its own default, so a
    default bound to the wrong declaration would pass the checks above.
    """
    answered = {k for k, d in _FIELD_DECLARATIONS.items() if d}
    assert answered <= set(_STOCHASTIC_RATES), (
        f"{sorted(answered - set(_STOCHASTIC_RATES))} answer a capability "
        "but no STOCHASTIC singleton builds them"
    )


# Pinned exemption set, not a ratchet: the fields whose DETERMINISTIC
# default does not follow the STOCHASTIC rate's direction (ARCH-18-001).
# permanent: RSH-07-001 (the status adoption gate defaults to requiring
# CASE_OWNER approval, ADR-0076)
DIRECTION_EXEMPTIONS: frozenset[FieldKey] = frozenset(
    {("StatusAuthorizationCallOutBundle", "status_adoption_gate_factory")}
)


def _directed_fields() -> list[FieldKey]:
    """Every default field outside :data:`DIRECTION_EXEMPTIONS`."""
    return sorted(
        (name, f.name)
        for name, bundle in _DEFAULTS.items()
        for f in dataclasses.fields(bundle)  # type: ignore[arg-type]
        if _key(bundle, f.name) not in DIRECTION_EXEMPTIONS
    )


@pytest.mark.spec("BT-23-002")
@pytest.mark.spec("BT-23-013")
@pytest.mark.parametrize("key", _directed_fields(), ids=_id)
def test_a_default_keeps_its_stochastic_direction(key: FieldKey) -> None:
    """Binding keeps BT-23-002's direction: a ceiling for a rate >= 0.5."""
    bundle_name, field = key
    bundle = _DEFAULTS[bundle_name]
    owner_key = _key(bundle, field)
    rates = _STOCHASTIC_RATES.get(owner_key, set())
    assert rates, f"{_id(owner_key)} has no STOCHASTIC node to compare with"
    ceiling = _backend(bundle, field).success_rate == 1.0  # type: ignore[attr-defined]
    for rate in rates:
        assert ceiling == (rate >= 0.5), (
            f"{_id(key)} defaults to a "
            f"{'ceiling' if ceiling else 'floor'} but its STOCHASTIC rate is "
            f"{rate} (BT-23-002)"
        )
