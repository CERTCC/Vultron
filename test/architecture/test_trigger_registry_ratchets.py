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

"""Architecture ratchets over the trigger registry (ADR-0110, TRIG-12-004).

The registry exists so these properties are read off a table instead of
asserted by inspection:

- **Use-case-to-row bijection.** The set of ``Svc*UseCase`` classes under
  ``vultron/core/use_cases/triggers/`` equals the set of ``use_case_class``
  values across rows — exact equality in both directions (ARCH-18-001), so a
  new use case with no row, or a row naming a class that moved away, fails.
- **The single non-BT-backed row.** Exactly one row has ``bt_backed=False``,
  it is ``SvcOfferCaseParticipantRoleUseCase``, and its result type declares
  no ``emitting_actor_id`` (ADR-0110 § Named exceptions).  The flag is also
  checked against the class hierarchy on every row.
- **Result binding.** Every row's ``request_model`` is a ``TriggerRequest``
  subclass bound to exactly the row's ``result_type``, which is what lets the
  one-method port return the verb's subtype (UCORG-05-006).
- **Data, not behavior.** No registry module defines a function or a class
  other than the row type's own validation, so the table cannot grow into
  the per-verb facade it replaced; every module stays under the CS-18-001
  line ceiling; every ``spec_ids`` entry resolves in the spec registry.

The class scan goes through ``_corpus`` (TB-13-001, TB-13-002) and never
imports the use-case modules to discover them; the rows are then compared by
class *name* against what the corpus found, and by *module* against the
package the corpus scanned.
"""

import ast
import inspect
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from test.architecture import _corpus
from vultron.core.models.use_case_result import TriggerResult
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers.requests import (
    TriggerRequest,
    result_type_of,
)
from vultron.trigger_registry import TriggerEntry, entries

_TRIGGERS_ROOT = (
    _corpus.REPO_ROOT / "vultron" / "core" / "use_cases" / "triggers"
)
_REGISTRY_ROOT = _corpus.REPO_ROOT / "vultron" / "trigger_registry"
_SPEC_DIR = _corpus.REPO_ROOT / "specs"

#: The naming convention the bijection is keyed on (``vultron/core/AGENTS.md``).
_SVC_USE_CASE_RE = re.compile(r"^Svc\w+UseCase$")

#: CS-18-001: a registry module is a table; it never needs to approach this.
_MODULE_LINE_CEILING = 500


def _svc_use_case_classes() -> dict[str, Path]:
    """``Svc*UseCase`` class name → defining file, from the corpus AST."""
    found: dict[str, Path] = {}
    for path, tree in _corpus.files_mentioning(
        "class Svc", under=_TRIGGERS_ROOT
    ):
        assert isinstance(tree, ast.Module)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and _SVC_USE_CASE_RE.match(
                node.name
            ):
                found[node.name] = path.relative_to(_corpus.REPO_ROOT)
    return found


def _rows() -> list[TriggerEntry]:
    rows = list(entries())
    assert rows, "the trigger registry has no rows — nothing to ratchet"
    return rows


def _row_ids() -> list[str]:
    return [row.verb for row in _rows()]


# ---------------------------------------------------------------------------
# (a) use-case-to-row bijection
# ---------------------------------------------------------------------------


@pytest.mark.spec("TRIG-12-004")
@pytest.mark.spec("ARCH-18-001")
def test_every_svc_use_case_has_exactly_one_row_and_vice_versa() -> None:
    """Exact set equality: the corpus's ``Svc*UseCase`` set is the rows' set.

    A subset check in either direction would let one side grow silently
    (ARCH-18-001); this is the executable form of TRIG-12-004's "every
    ``Svc*UseCase`` class under ``triggers/`` MUST appear in exactly one row".
    """
    in_code = _svc_use_case_classes()
    assert in_code, f"no Svc*UseCase classes found under {_TRIGGERS_ROOT}"
    in_rows = {row.use_case_class.__name__ for row in _rows()}
    assert set(in_code) == in_rows, (
        "Svc*UseCase classes and registry rows disagree.\n"
        f"  in code, no row:   {sorted(set(in_code) - in_rows)}\n"
        f"  in rows, no class: {sorted(in_rows - set(in_code))}"
    )


@pytest.mark.spec("TRIG-12-004")
@pytest.mark.parametrize("row", _rows(), ids=_row_ids())
def test_row_use_case_class_lives_under_triggers(row: TriggerEntry) -> None:
    """The class a row names is the one the corpus scanned, not a namesake."""
    module = row.use_case_class.__module__
    assert module.startswith("vultron.core.use_cases.triggers."), (
        f"row {row.verb!r}: {row.use_case_class.__name__} is defined in"
        f" {module}, outside vultron/core/use_cases/triggers/ (UCORG-01-002)"
    )


@pytest.mark.spec("TRIG-12-004")
def test_each_use_case_appears_in_rows_that_agree_on_result_type() -> None:
    """A use case named by several rows (the demo ``notify-*`` verbs) has one
    result type — otherwise the response contract would depend on the verb."""
    by_class: dict[str, set[str]] = {}
    for row in _rows():
        by_class.setdefault(row.use_case_class.__name__, set()).add(
            row.result_type.__name__
        )
    disagreeing = {k: v for k, v in by_class.items() if len(v) > 1}
    assert disagreeing == {}, disagreeing


# ---------------------------------------------------------------------------
# (b) the single non-BT-backed row
# ---------------------------------------------------------------------------


@pytest.mark.spec("TRIG-12-004")
@pytest.mark.spec("UCORG-05-005")
def test_exactly_one_row_is_not_bt_backed_and_it_is_the_role_offer() -> None:
    """ADR-0110 § Named exceptions: one pinned non-BT-backed verb.

    Its body carries no ``emitting_actor_id`` because it never ran through
    ``SvcBTTriggerBase``; bringing it under the base would add a key to a live
    response body and needs its own decision.
    """
    non_bt = [row for row in _rows() if not row.bt_backed]
    assert [row.use_case_class.__name__ for row in non_bt] == [
        "SvcOfferCaseParticipantRoleUseCase"
    ], f"non-BT-backed rows: {[r.verb for r in non_bt]}"
    (row,) = non_bt
    assert row.verb == "offer-case-participant-role"
    assert "emitting_actor_id" not in row.result_type.model_fields, (
        f"{row.result_type.__name__} declares emitting_actor_id, which only a"
        " SvcBTTriggerBase verb can fill"
    )


@pytest.mark.spec("TRIG-12-004")
@pytest.mark.parametrize("row", _rows(), ids=_row_ids())
def test_bt_backed_flag_matches_the_class_hierarchy(row: TriggerEntry) -> None:
    """``bt_backed`` is what the dispatcher keys port injection on, so it must
    describe the class rather than restate a belief about it."""
    assert row.bt_backed is issubclass(row.use_case_class, SvcBTTriggerBase)


@pytest.mark.spec("UCORG-05-005")
@pytest.mark.parametrize("row", _rows(), ids=_row_ids())
def test_every_row_result_type_forbids_unknown_keys(row: TriggerEntry) -> None:
    """Each verb's result is a ``TriggerResult`` subtype that forbids unknown
    keys — a use case that grows a return key fails loudly (UCORG-05-005)."""
    assert issubclass(row.result_type, TriggerResult)
    assert row.result_type.model_config.get("extra") == "forbid"


#: The keyword ports ``RegistryTriggerDispatcher`` injects, by ``bt_backed``.
_BT_PORT_KWARGS = frozenset(
    {"trigger_activity", "wire_render_port", "sync_port"}
)
_PLAIN_PORT_KWARGS = frozenset({"trigger_activity"})


@pytest.mark.spec("TRIG-12-004")
@pytest.mark.parametrize("row", _rows(), ids=_row_ids())
def test_row_constructor_accepts_the_port_bundle_its_flag_earns(
    row: TriggerEntry,
) -> None:
    """``(dl, request, **ports)`` must be a legal call for every row.

    The dispatcher hands a BT-backed use case ``trigger_activity``,
    ``wire_render_port`` and ``sync_port``, and the non-BT-backed one
    ``trigger_activity`` alone; a subclass that overrides ``__init__`` and
    drops a keyword would turn its row into a ``TypeError`` at dispatch.
    """
    params = inspect.signature(row.use_case_class).parameters
    accepts_var_kw = any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
    )
    wanted = _BT_PORT_KWARGS if row.bt_backed else _PLAIN_PORT_KWARGS
    missing = (
        {k for k in wanted if k not in params} if not accepts_var_kw else set()
    )
    assert not missing, (
        f"{row.use_case_class.__name__} (verb {row.verb!r}) does not accept"
        f" {sorted(missing)}; the dispatcher injects them"
    )
    positional = [
        name
        for name, p in params.items()
        if p.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    assert positional[:2] == ["dl", "request"], positional


# ---------------------------------------------------------------------------
# (c) request-model result binding
# ---------------------------------------------------------------------------


@pytest.mark.spec("UCORG-05-006")
@pytest.mark.spec("TRIG-12-004")
@pytest.mark.parametrize("row", _rows(), ids=_row_ids())
def test_row_request_model_binds_exactly_the_rows_result_type(
    row: TriggerEntry,
) -> None:
    """The request binds ``ResultT_co`` to the row's ``result_type``.

    This is the property the one-method ``TriggerDispatcher.trigger()`` rests
    on: a call site's static result type is the row's runtime one.
    """
    assert issubclass(row.request_model, TriggerRequest)
    assert row.request_model is not TriggerRequest
    assert result_type_of(row.request_model) is row.result_type, (
        f"row {row.verb!r}: {row.request_model.__name__} binds"
        f" {result_type_of(row.request_model).__name__}, row says"
        f" {row.result_type.__name__}"
    )


# ---------------------------------------------------------------------------
# Data, not behavior (TRIG-12-004's last sentence)
# ---------------------------------------------------------------------------


def _registry_modules() -> Iterator[tuple[Path, ast.Module, str]]:
    sources = dict(_corpus.all_sources(under=_REGISTRY_ROOT))
    for path, tree in _corpus.all_trees(under=_REGISTRY_ROOT):
        assert isinstance(tree, ast.Module)
        yield path.relative_to(_corpus.REPO_ROOT), tree, sources[path]


@pytest.mark.spec("TRIG-12-004")
def test_domain_modules_hold_rows_only() -> None:
    """No domain sub-module defines a function or class: rows and constants.

    ``_entry.py`` (the row type and its index) and ``__init__.py`` (assembly,
    the lookup and the enumeration) are the only modules allowed definitions,
    and their allowance is listed here so a new function has to be argued for.
    """
    allowed_defs: dict[str, set[str]] = {
        "vultron/trigger_registry/_entry.py": {
            "TriggerExposure",
            "TriggerEntry",
            "index_by_request_model",
            "_iter_duplicate_verbs",
        },
        "vultron/trigger_registry/__init__.py": {"entries", "lookup_entry"},
    }
    offenders: list[str] = []
    for rel, tree, _ in _registry_modules():
        defs = {
            node.name
            for node in tree.body
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            )
        }
        extra = defs - allowed_defs.get(rel.as_posix(), set())
        if extra:
            offenders.append(f"{rel}: {sorted(extra)}")
    assert offenders == [], (
        "registry modules define behavior beyond the row type and lookups"
        " (TRIG-12-004):\n" + "\n".join(offenders)
    )


@pytest.mark.spec("TRIG-12-004")
def test_row_type_carries_no_per_verb_methods() -> None:
    """``TriggerEntry`` has one method of its own: its construction check."""
    for rel, tree, _ in _registry_modules():
        if rel.name != "_entry.py":
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "TriggerEntry":
                methods = [
                    child.name
                    for child in node.body
                    if isinstance(child, ast.FunctionDef)
                ]
                assert methods == ["__post_init__"], methods
                return
    pytest.fail("TriggerEntry not found in vultron/trigger_registry/_entry.py")


@pytest.mark.spec("CS-18-001")
def test_registry_modules_stay_under_the_line_ceiling() -> None:
    over = [
        f"{rel}: {source.count(chr(10))} lines"
        for rel, _, source in _registry_modules()
        if source.count("\n") > _MODULE_LINE_CEILING
    ]
    assert over == [], over


@pytest.mark.spec("TRIG-12-004")
@pytest.mark.spec_corpus
def test_every_row_spec_id_resolves_in_the_spec_registry() -> None:
    """A row's ``spec_ids`` are the requirements its verb implements; a typo'd
    or retired ID would otherwise sit in the table forever (SR-04-011)."""
    from vultron.metadata.specs.registry import load_registry

    known = load_registry(_SPEC_DIR).all_specs
    unresolved = sorted(
        f"{row.verb}: {spec_id}"
        for row in _rows()
        for spec_id in row.spec_ids
        if spec_id not in known
    )
    assert unresolved == [], unresolved
