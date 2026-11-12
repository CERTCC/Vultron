"""Architecture check: a docs page shows the committed vocab example.

The ``python exec`` blocks under ``docs/`` render vocab examples at site
build time.  A block that called a builder itself ran it outside the example
id scope, so every id, ``published``, ``updated`` and ``genesisHash`` it
showed was drawn afresh on each build and disagreed with the committed
``docs/reference/examples/<name>.json`` (#5893).  Every such block now calls
``render_example("<name>")``, which builds the example the way the generator
does.  This module holds that in place:

- no exec block imports a vocab example builder, only ``render_example``;
- every name a page renders is a committed example, and what it renders is
  that file's text;
- rendering is the same twice in one process and in a fresh process.

AC-1, AC-2 and AC-3 of issue #5893.
"""

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

import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from vultron.metadata.markdown_tables import exec_blocks
from vultron.wire.as2.vocab.examples.vocab_examples import (
    example_names,
    render_example,
)

_REPO_ROOT = Path(__file__).parents[2]
_DOCS = _REPO_ROOT / "docs"
_COMMITTED_DIR = _DOCS / "reference" / "examples"

_EXAMPLES_PACKAGE = "vultron.wire.as2.vocab.examples"
_RENDERER = "render_example"

#: Example-package modules a docs block may import from freely.  The tutorial
#: module renders the tutorial's own shell commands and payload, not a
#: committed vocab example, so it has no artifact to agree with.
_OTHER_RENDERERS = frozenset({f"{_EXAMPLES_PACKAGE}.submit_report_tutorial"})


@dataclass(frozen=True, slots=True)
class _Block:
    """One exec block under ``docs/``, located for a failure message."""

    where: str
    code: str


def _in_examples_package(module: str) -> bool:
    return (
        module == _EXAMPLES_PACKAGE
        or module.startswith(f"{_EXAMPLES_PACKAGE}.")
    ) and module not in _OTHER_RENDERERS


def direct_builder_uses(code: str) -> list[str]:
    """What in *code* reaches a vocab example other than ``render_example``.

    An import of any other name from the examples package is one: through it
    a block can build an example outside the id scope.  So is a plain
    ``import`` of a module in it, which reaches every builder as an attribute.
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if _in_examples_package(node.module):
                found += [
                    f"from {node.module} import {alias.name}"
                    for alias in node.names
                    if alias.name != _RENDERER
                ]
        elif isinstance(node, ast.Import):
            found += [
                f"import {alias.name}"
                for alias in node.names
                if _in_examples_package(alias.name)
            ]
    return found


def rendered_names(code: str) -> list[str | None]:
    """The name each ``render_example`` call in *code* renders.

    ``None`` stands for a call whose name is not a string literal, which
    this gate cannot compare with a committed file.
    """
    names: list[str | None] = []
    for node in ast.walk(ast.parse(code)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == _RENDERER
        ):
            first = node.args[0] if node.args else None
            if isinstance(first, ast.Constant) and isinstance(
                first.value, str
            ):
                names.append(first.value)
            else:
                names.append(None)
    return names


@pytest.fixture(scope="module")
def docs_blocks() -> list[_Block]:
    """Every exec block in every Markdown page under ``docs/``."""
    blocks: list[_Block] = []
    for path in sorted(_DOCS.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for block in exec_blocks(text):
            where = f"{path.relative_to(_REPO_ROOT)}:{block.line}"
            blocks.append(_Block(where=where, code=block.code))
    return blocks


def _committed_markdown(name: str) -> str:
    """The committed example *name* as ``json2md`` frames it."""
    text = (_COMMITTED_DIR / f"{name}.json").read_bytes().decode("utf-8")
    return f"```json\n{text}\n```"


@pytest.mark.spec("DF-09-009")
def test_no_exec_block_calls_a_vocab_example_builder(docs_blocks):
    """An exec block reaches a vocab example only through ``render_example``."""
    assert docs_blocks, (
        "no exec block found under docs/, so nothing was checked"
    )
    offenders = [
        f"{block.where}: {use}"
        for block in docs_blocks
        for use in direct_builder_uses(block.code)
    ]
    assert not offenders, (
        "These exec blocks build a vocab example outside the example id "
        "scope, so the page would show fresh ids and stamps. Render it with "
        'render_example("<name>") instead:\n  ' + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    "code",
    [
        "from vultron.wire.as2.vocab.examples.vocab_examples import "
        "create_case, json2md\nprint(json2md(create_case()))",
        "from vultron.wire.as2.vocab.examples.case import create_case\n",
        "import vultron.wire.as2.vocab.examples.vocab_examples as v\n"
        "print(v.json2md(v.create_case()))",
    ],
    ids=["builder-import", "builder-module", "module-import"],
)
def test_the_check_flags_a_direct_builder_call(code):
    assert direct_builder_uses(code)


@pytest.mark.parametrize(
    "code",
    [
        "from vultron.wire.as2.vocab.examples.vocab_examples import "
        'render_example\nprint(render_example("create_case"))',
        "from vultron.wire.as2.vocab.examples.submit_report_tutorial "
        "import render_payload\nprint(render_payload())",
        "from vultron.metadata.docs import render_catalog\n",
    ],
    ids=["renderer", "tutorial", "unrelated"],
)
def test_the_check_passes_a_block_that_renders_through_the_renderer(code):
    assert direct_builder_uses(code) == []


@pytest.mark.spec("DF-09-009")
def test_every_rendered_example_is_the_committed_artifact(docs_blocks):
    """A page's rendered example is the committed file, byte for byte."""
    uses = [
        (block.where, name)
        for block in docs_blocks
        for name in rendered_names(block.code)
    ]
    assert uses, (
        "no render_example call found under docs/, so nothing was compared"
    )
    not_literal = [where for where, name in uses if name is None]
    assert not not_literal, (
        "render_example must name its example with a string literal, so "
        "this gate can compare it with the committed file:\n  "
        + "\n  ".join(not_literal)
    )
    known = set(example_names())
    unknown = sorted(
        f"{where}: {name}" for where, name in uses if name not in known
    )
    assert not unknown, (
        "These pages render an example the generator does not write:\n  "
        + "\n  ".join(unknown)
    )
    drifted = sorted(
        name
        for name in {name for _, name in uses if name is not None}
        if render_example(name) != _committed_markdown(name)
    )
    assert not drifted, (
        "These rendered examples differ from docs/reference/examples/. "
        "Re-run uv run python vultron/wire/as2/vocab/examples/"
        "vocab_examples.py and commit the result:\n  " + "\n  ".join(drifted)
    )


def test_every_example_renders_the_same_twice_and_as_committed():
    """Two renderings in one process agree, and agree with the artifact."""
    names = example_names()
    assert names, "the generator names no example, so nothing was compared"
    unstable = [
        name for name in names if render_example(name) != render_example(name)
    ]
    assert not unstable, "rendered differently twice: " + ", ".join(unstable)
    drifted = [
        name
        for name in names
        if render_example(name) != _committed_markdown(name)
    ]
    assert not drifted, "differs from the committed file: " + ", ".join(
        drifted
    )


_RENDER_ALL = (
    "import json\n"
    "from vultron.wire.as2.vocab.examples.vocab_examples import (\n"
    "    example_names, render_example,\n"
    ")\n"
    "print(json.dumps({n: render_example(n) for n in example_names()}))\n"
)


def test_a_fresh_process_renders_every_example_the_same():
    """Rendering does not depend on what this process has already built."""
    result = subprocess.run(
        [sys.executable, "-c", _RENDER_ALL],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=300,
    )
    fresh: dict[str, str] = json.loads(result.stdout)
    here = {name: render_example(name) for name in example_names()}
    assert fresh.keys() == here.keys()
    differ = sorted(name for name in here if fresh[name] != here[name])
    assert not differ, "rendered differently in a fresh process: " + ", ".join(
        differ
    )


def test_render_example_refuses_a_name_the_generator_does_not_write():
    with pytest.raises(ValueError, match="no committed example"):
        render_example("no_such_example")
