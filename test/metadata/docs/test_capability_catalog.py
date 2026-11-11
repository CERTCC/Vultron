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
"""Tests for the generated capability catalog (#3425).

``docs/topics/capability_model/index.md`` renders one catalog table per
domain from the core capability declarations (BT-18-020, BT-18-021).  These
tests pin that the page's blocks name every declaration module exactly once,
that the capability names its hand-written summary table cites are declared,
and that the renderer refuses what it cannot render instead of publishing a
blank row (MS-16-002, MS-16-003).
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import re
from collections import Counter
from pathlib import Path
from typing import cast

import pytest
from py_trees.ports import PortInformation

from vultron.core.behaviors.call_out.capabilities import (
    capability_declarations,
)
from vultron.core.behaviors.call_out.capability import (
    ActuatorCapability,
    Capability,
    EvaluatorCapability,
)
from vultron.metadata.base import repo_root
from vultron.metadata.docs.capability_catalog import (
    TABLE_HEADER,
    CapabilityCatalogError,
    capability_name,
    declaration_module,
    declarations_by_module,
    render_capability_table,
    render_row,
    summary,
)

PAGE = Path("docs/topics/capability_model/index.md")

_EXEC_BLOCK = re.compile(
    r'^```python exec="true"[^\n]*\n(.*?)^```', re.M | re.S
)


def _page_text() -> str:
    return (repo_root() / PAGE).read_text(encoding="utf-8")


def _rendered_modules(text: str) -> list[str]:
    """Every module a ``render_capability_table`` call on the page names."""
    modules: list[str] = []
    for block in _EXEC_BLOCK.findall(text):
        for node in ast.walk(ast.parse(block)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "render_capability_table"
            ):
                for arg in node.args:
                    assert isinstance(arg, ast.Constant) and isinstance(
                        arg.value, str
                    ), "name each declaration module as a string literal"
                    modules.append(arg.value)
    return modules


def _summary_table_names(text: str) -> set[str]:
    """The capability names linked in the page's "Vultron doesn't" table."""
    start = text.index('| "Vultron doesn')
    table = text[start : text.index("\n\n", start)]
    names: set[str] = set()
    for link_text in re.findall(r"\[([^\]]+)\]\(#", table):
        names.update(
            n.strip() for n in link_text.split(",") if n.strip() != "Sentinel"
        )
    return names


# --- the page against the roster ------------------------------------------


@pytest.mark.spec("MS-16-003")
def test_page_renders_every_declaration_module_exactly_once() -> None:
    named = Counter(_rendered_modules(_page_text()))
    twice = sorted(m for m, n in named.items() if n > 1)
    assert not twice, f"named in more than one catalog block: {twice}"
    roster = set(declarations_by_module())
    assert not roster - set(named), (
        f"declaration modules with no catalog block on {PAGE}: "
        f"{sorted(roster - set(named))}; add a domain section for each"
    )
    assert not set(named) - roster, (
        f"catalog blocks on {PAGE} name modules that declare nothing: "
        f"{sorted(set(named) - roster)}"
    )


def test_every_catalog_block_renders() -> None:
    for module in _rendered_modules(_page_text()):
        assert render_capability_table(module).count("\n| `") >= 1


@pytest.mark.spec("MS-16-003")
def test_summary_table_names_only_declared_capabilities() -> None:
    names = _summary_table_names(_page_text())
    assert names, "the summary table parser found no capability names"
    declared = {capability_name(d) for d in capability_declarations()}
    assert not names - declared, (
        f"the summary table on {PAGE} cites capabilities with no core "
        f"declaration: {sorted(names - declared)}"
    )


def test_page_parsers_find_what_they_parse() -> None:
    """Guard the two ratchets above against passing on nothing."""
    text = _page_text()
    assert len(_rendered_modules(text)) == len(declarations_by_module())
    assert "EvaluateReportCredibility" in _summary_table_names(text)


def _subclasses(cls: type[Capability]) -> list[type[Capability]]:
    found: list[type[Capability]] = []
    for sub in cls.__subclasses__():
        found += [sub, *_subclasses(sub)]
    return found


def test_each_fuzzer_node_sits_at_its_declaration_module_path() -> None:
    """The catalog page and the wiring guide both tell a reader so."""
    import vultron.demo.fuzzer as fuzzer_pkg

    for info in pkgutil.walk_packages(
        fuzzer_pkg.__path__, prefix=f"{fuzzer_pkg.__name__}."
    ):
        importlib.import_module(info.name)
    for declaration in capability_declarations():
        expected = f"{fuzzer_pkg.__name__}.{declaration_module(declaration)}"
        modules = {
            sub.__module__
            for sub in _subclasses(declaration)
            if sub.__module__.startswith(f"{fuzzer_pkg.__name__}.")
        }
        assert modules == {expected}, (
            f"{declaration.__qualname__}: fuzzer nodes in {sorted(modules)}, "
            f"expected {expected}"
        )


# --- the renderer ----------------------------------------------------------


def test_every_declaration_renders_a_row() -> None:
    for declaration in capability_declarations():
        row = render_row(declaration)
        assert row.startswith(f"| `{capability_name(declaration)}` |")
        assert f"| {declaration.shape.value} |" in row
        assert summary(declaration) in row


def test_table_lists_the_module_rows_in_the_order_named() -> None:
    grouped = declarations_by_module()
    first, second = "report_management.validate", "case_management"
    text = render_capability_table(first, second)
    lines = text.splitlines()
    assert lines[0].startswith("Declared in ")
    assert "report_management/validate.py" in lines[0]
    assert tuple(lines[2:4]) == TABLE_HEADER
    expected = [render_row(d) for d in (*grouped[first], *grouped[second])]
    assert lines[4:] == expected


def test_ports_render_with_their_types() -> None:
    from vultron.core.behaviors.call_out.capabilities.report_management.publication.advisory import (
        ReviewAdvisoryDraftCapability,
    )

    row = render_row(ReviewAdvisoryDraftCapability)
    assert "`draft_advisory_artifact` (`str`)" in row
    assert "`advisory_review_decision` (`AdvisoryReviewDecision`)" in row


def _declare(
    base: type[Capability],
    name: str,
    doc: str | None,
    **attributes: object,
) -> type[Capability]:
    namespace: dict[str, object] = {"__module__": __name__, **attributes}
    if doc is not None:
        namespace["__doc__"] = doc
    return cast(type[Capability], type(name, (base,), namespace))


def test_portless_capabilities_say_what_their_answer_is() -> None:
    actuator = _declare(ActuatorCapability, "PokeCapability", "Poke it.")
    evaluator = _declare(EvaluatorCapability, "JudgeCapability", "Judge it.")
    assert render_row(actuator).endswith("| — | side effect only |")
    assert render_row(evaluator).endswith("| — | verdict only |")


def test_summary_is_the_first_paragraph_on_one_line_as_markdown() -> None:
    cls = _declare(
        EvaluatorCapability,
        "WrapCapability",
        """Decide whether to admit an inbound ``Create(X)``, or
        not | ever.

        Blackboard contract (BT-18-001):
          Output keys: (none)
        """,
    )
    assert summary(cls) == (
        r"Decide whether to admit an inbound `Create(X)`, or not \| ever."
    )


@pytest.mark.parametrize("doc", [None, "   "])
def test_a_declaration_with_no_docstring_is_refused(doc: str | None) -> None:
    cls = _declare(EvaluatorCapability, "BlankCapability", doc)
    with pytest.raises(CapabilityCatalogError, match="no docstring"):
        summary(cls)


def test_a_class_name_without_the_suffix_is_refused() -> None:
    cls = _declare(EvaluatorCapability, "Judge", "Judge it.")
    with pytest.raises(CapabilityCatalogError, match="does not end in"):
        capability_name(cls)


def test_a_declaration_outside_the_package_is_refused() -> None:
    cls = _declare(EvaluatorCapability, "StrayCapability", "Stray.")
    with pytest.raises(CapabilityCatalogError, match="outside"):
        declaration_module(cls)


@pytest.mark.parametrize(
    ("modules", "message"),
    [
        ((), "at least one"),
        (("case_management", "case_management"), "named twice"),
        (("no_such_module",), "declare no capability"),
    ],
)
def test_a_bad_module_list_is_refused(
    modules: tuple[str, ...], message: str
) -> None:
    with pytest.raises(CapabilityCatalogError, match=message):
        render_capability_table(*modules)


def test_an_injected_roster_is_rendered() -> None:
    cls = _declare(
        EvaluatorCapability,
        "OnlyCapability",
        "Only one.",
        OUTPUT_PORTS={"x": PortInformation(data_type=int, required=True)},
    )
    text = render_capability_table("m", grouped={"m": (cls,)})
    assert "| `Only` | Evaluator | Only one. | — | `x` (`int`) |" in text
