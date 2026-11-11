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
import contextlib
import io
import re
import textwrap
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest
from markdown.extensions.toc import slugify  # type: ignore[import-untyped]
from py_trees.ports import PortInformation

from test.support.fuzzer_nodes import FUZZER_PACKAGE, fuzzer_capability_classes
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

#: A fenced block's opening line; the info string is group 2.
_FENCE = re.compile(r"^([ \t]*)(`{3,}|~{3,})([^\n]*)$", re.M)
_HEADING = re.compile(r"^(#{2,3}) (.+)$", re.M)
_RENDER = "render_capability_table"


@dataclass(frozen=True)
class _Block:
    """One markdown-exec block on the page, under the heading *anchor*."""

    anchor: str
    source: str
    modules: tuple[str, ...]


def _page_text() -> str:
    return (repo_root() / PAGE).read_text(encoding="utf-8")


def _render_args(source: str) -> list[tuple[str, ...]]:
    """The module arguments of each ``render_capability_table`` call."""
    calls: list[tuple[str, ...]] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == _RENDER
        ):
            args: list[str] = []
            for arg in node.args:
                assert isinstance(arg, ast.Constant) and isinstance(
                    arg.value, str
                ), "name each declaration module as a string literal"
                args.append(arg.value)
            calls.append(tuple(args))
    return calls


def _exec_blocks(text: str) -> list[_Block]:
    """Every fenced block whose info string sets ``exec``, any value or
    indent, with the anchor of the heading it sits under."""
    blocks: list[_Block] = []
    headings = [
        (m.start(), slugify(m.group(2), "-")) for m in _HEADING.finditer(text)
    ]
    pos = 0
    while (opening := _FENCE.search(text, pos)) is not None:
        indent, fence, info = opening.groups()
        closing = re.compile(
            rf"^{re.escape(indent)}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*$",
            re.M,
        ).search(text, opening.end())
        assert closing is not None, f"unclosed fence at {opening.start()}"
        if re.search(r"\bexec=", info):
            body = text[opening.end() + 1 : closing.start()]
            source = textwrap.dedent(body)
            anchor = next(
                (
                    a
                    for start, a in reversed(headings)
                    if start < opening.start()
                ),
                "",
            )
            calls = _render_args(source)
            modules = tuple(m for call in calls for m in call)
            blocks.append(_Block(anchor, source, modules))
        pos = closing.end()
    return blocks


def _catalog_blocks(text: str) -> list[_Block]:
    return [b for b in _exec_blocks(text) if _RENDER in b.source]


def _summary_rows(text: str) -> list[tuple[list[tuple[str, str]], set[str]]]:
    """Each row of the "Vultron doesn't" table: its (name, anchor) links and
    its Shape cell."""
    start = text.index('| "Vultron doesn')
    table = text[start : text.index("\n\n", start)].splitlines()[2:]
    rows: list[tuple[list[tuple[str, str]], set[str]]] = []
    for line in table:
        cells = line.split("|")
        assert len(cells) == 5, f"unexpected summary table row: {line!r}"
        where, shapes = cells[2], cells[3]
        links = [
            (name.strip(), anchor)
            for names, anchor in re.findall(r"\[([^\]]+)\]\(#([^)]+)\)", where)
            if names != "Sentinel"
            for name in names.split(",")
        ]
        rows.append((links, {s.strip() for s in shapes.split(",")}))
    return rows


# --- the page against the roster ------------------------------------------


@pytest.mark.spec("MS-16-003")
def test_page_renders_every_declaration_module_exactly_once() -> None:
    named = Counter(
        m for b in _catalog_blocks(_page_text()) for m in b.modules
    )
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


def test_every_exec_fence_on_the_page_is_parsed() -> None:
    """A fence the parser skipped would hide its modules from the check."""
    text = _page_text()
    openers = [
        m for m in _FENCE.finditer(text) if re.search(r"\bexec=", m.group(3))
    ]
    assert len(_exec_blocks(text)) == len(openers) > 0


def test_each_catalog_block_prints_its_tables() -> None:
    """Run each block as the build does: it must print, not only call."""
    for block in _catalog_blocks(_page_text()):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(compile(block.source, str(PAGE), "exec"), {})  # noqa: S102
        expected = "".join(
            render_capability_table(*call)
            for call in _render_args(block.source)
        )
        assert out.getvalue().strip() == expected.strip(), (
            f"the block under #{block.anchor} does not print its table"
        )


@pytest.mark.spec("MS-16-003")
def test_summary_table_matches_the_declarations() -> None:
    """Names are declared, Shape cells are their shapes, links reach the
    section that renders them."""
    text = _page_text()
    rows = _summary_rows(text)
    assert rows, "the summary table parser found no rows"
    declared = {capability_name(d): d for d in capability_declarations()}
    sections: dict[str, set[str]] = {}
    for block in _catalog_blocks(text):
        sections.setdefault(block.anchor, set()).update(block.modules)
    for links, shapes in rows:
        if not links:
            continue
        names = [name for name, _ in links]
        unknown = sorted(set(names) - set(declared))
        assert not unknown, (
            f"the summary table on {PAGE} cites capabilities with no core "
            f"declaration: {unknown}"
        )
        assert shapes == {declared[n].shape.value for n in names}, (
            f"Shape cell {sorted(shapes)} does not match {names}"
        )
        for name, anchor in links:
            assert declaration_module(declared[name]) in sections.get(
                anchor, set()
            ), f"#{anchor} does not render {name}"


def test_page_parsers_find_what_they_parse() -> None:
    """Guard the ratchets above against passing on nothing."""
    text = _page_text()
    assert len(_catalog_blocks(text)) > 1
    linked = {name for links, _ in _summary_rows(text) for name, _ in links}
    assert "EvaluateReportCredibility" in linked


def test_each_fuzzer_node_sits_at_its_declaration_module_path() -> None:
    """The catalog page and the wiring guide both tell a reader so."""
    found: dict[type[Capability], set[str]] = {}
    for node in fuzzer_capability_classes():
        if declaration := node.declaration():
            found.setdefault(declaration, set()).add(node.__module__)
    for declaration in capability_declarations():
        expected = f"{FUZZER_PACKAGE}.{declaration_module(declaration)}"
        assert found.get(declaration) == {expected}, (
            f"{declaration.__qualname__}: fuzzer nodes in "
            f"{sorted(found.get(declaration, set()))}, expected {expected}"
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


@pytest.mark.parametrize("name", ["Judge", "Capability"])
def test_a_class_name_without_a_capability_name_is_refused(name: str) -> None:
    cls = _declare(EvaluatorCapability, name, "Judge it.")
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


def test_several_ports_are_listed_one_per_line() -> None:
    cls = _declare(
        EvaluatorCapability,
        "PairCapability",
        "Pair.",
        INPUT_PORTS={
            "c": PortInformation(data_type=float, required=True),
            "d": PortInformation(data_type=bytes, required=False),
        },
        OUTPUT_PORTS={
            "a": PortInformation(data_type=int, required=True),
            "b": PortInformation(data_type=str, required=True),
        },
    )
    assert render_row(cls).endswith(
        "| `c` (`float`)<br>`d` (`bytes`) | `a` (`int`)<br>`b` (`str`) |"
    )


def test_cross_reference_roles_render_as_code() -> None:
    cls = _declare(
        EvaluatorCapability,
        "RoleCapability",
        "Read :class:`~vultron.core.models.Case` and :func:`a.b.run`.",
    )
    assert summary(cls) == "Read `Case` and `a.b.run`."


def test_a_blank_line_holding_spaces_still_ends_the_summary() -> None:
    cls = _declare(
        EvaluatorCapability, "GapCapability", "First.\n   \nSecond."
    )
    assert summary(cls) == "First."


def test_the_declared_in_line_names_the_real_source_file() -> None:
    cls = _declare(EvaluatorCapability, "HereCapability", "Here.")
    text = render_capability_table("m", grouped={"m": (cls,)})
    assert text.startswith(
        "Declared in `test/metadata/docs/test_capability_catalog.py`."
    )
    real = render_capability_table("case_management")
    assert real.startswith(
        "Declared in "
        "`vultron/core/behaviors/call_out/capabilities/case_management.py`."
    )


def test_a_module_with_no_declarations_is_refused() -> None:
    with pytest.raises(CapabilityCatalogError, match="declare no capability"):
        render_capability_table("empty", grouped={"empty": ()})
