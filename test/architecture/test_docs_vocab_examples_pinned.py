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

from test.architecture import _corpus
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


def _in_examples_package(name: str) -> bool:
    """Whether *name* is the examples package or a name inside it.

    The tutorial module, and any name inside it, is not (:data:`_OTHER_RENDERERS`).
    """
    if any(
        name == other or name.startswith(f"{other}.")
        for other in _OTHER_RENDERERS
    ):
        return False
    return name == _EXAMPLES_PACKAGE or name.startswith(
        f"{_EXAMPLES_PACKAGE}."
    )


def _reaches_examples(name: str) -> bool:
    """Whether importing *name* gives a block the examples package.

    The package and anything in it does, and so does each package above it
    (``vultron.wire.as2.vocab``), whose attributes reach every builder.
    """
    return _in_examples_package(name) or _EXAMPLES_PACKAGE.startswith(
        f"{name}."
    )


def direct_builder_uses(code: str) -> list[str]:
    """What in *code* reaches a vocab example other than ``render_example``.

    Any import that reaches the examples package is one (:func:`_reaches_examples`),
    except ``render_example`` itself imported under its own name: through
    anything else a block can build an example outside the id scope.  A
    string naming the package is one too, since ``importlib`` or
    ``__import__`` can load a builder from it.  A renamed ``render_example``
    is one because :func:`rendered_names` could no longer see its calls.
    """
    found: list[str] = []
    for node in ast.walk(_corpus.parse_inline(code)):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            for alias in node.names:
                target = f"{node.module}.{alias.name}"
                is_renderer = (
                    _in_examples_package(node.module)
                    and alias.name == _RENDERER
                    and alias.asname in (None, _RENDERER)
                )
                if _reaches_examples(target) and not is_renderer:
                    shown = f" as {alias.asname}" if alias.asname else ""
                    found.append(
                        f"from {node.module} import {alias.name}{shown}"
                    )
        elif isinstance(node, ast.Import):
            found += [
                f"import {alias.name}"
                for alias in node.names
                if _reaches_examples(alias.name)
            ]
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _in_examples_package(node.value.strip())
        ):
            found.append(f"a string naming {node.value.strip()!r}")
    return found


def rendered_names(code: str) -> list[str | None]:
    """The name each ``render_example`` call in *code* renders.

    ``None`` stands for a call whose name is not a string literal, which
    this gate cannot compare with a committed file.
    """
    names: list[str | None] = []
    for node in ast.walk(_corpus.parse_inline(code)):
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


def _committed_markdown(
    name: str, committed_dir: Path = _COMMITTED_DIR
) -> str:
    """The committed example *name* as ``json2md`` frames it."""
    text = (committed_dir / f"{name}.json").read_bytes().decode("utf-8")
    return f"```json\n{text}\n```"


def rendering_problems(
    uses: list[tuple[str, str | None]],
    committed_dir: Path = _COMMITTED_DIR,
) -> list[str]:
    """What is wrong with *uses*, each a ``(where, rendered name)`` pair.

    A name that is not a literal cannot be compared; a name the generator
    does not write has no artifact; and a rendering that differs from the
    committed file is the drift this gate exists for.
    """
    known = set(example_names())
    problems = [
        f"{where}: render_example's name is not a string literal"
        for where, name in uses
        if name is None
    ]
    problems += [
        f"{where}: {name!r} is not an example the generator writes"
        for where, name in uses
        if name is not None and name not in known
    ]
    rendered = sorted({name for _, name in uses if name in known})
    problems += [
        f"{name}: the page's rendering differs from {name}.json"
        for name in rendered
        if render_example(name) != _committed_markdown(name, committed_dir)
    ]
    return problems


@pytest.fixture(scope="module")
def docs_blocks() -> list[_Block]:
    """Every exec block in every Markdown page under ``docs/``.

    Read through the shared docs cache, as every docs ratchet is (TB-13-003).
    """
    blocks: list[_Block] = []
    for path, text in _corpus.all_docs():
        for block in exec_blocks(text):
            where = f"{path.relative_to(_REPO_ROOT)}:{block.line}"
            blocks.append(_Block(where=where, code=block.code))
    return blocks


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
        "from vultron.wire.as2.vocab import examples\n",
        "import vultron.wire.as2.vocab\n",
        "import importlib\n"
        "m = importlib.import_module("
        "'vultron.wire.as2.vocab.examples.vocab_examples')\n",
        "from vultron.wire.as2.vocab.examples.vocab_examples import "
        "render_example as r\nprint(r('create_case'))",
    ],
    ids=[
        "builder-import",
        "builder-module",
        "module-import",
        "parent-package-from",
        "parent-package-import",
        "importlib",
        "renamed-renderer",
    ],
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
        "import vultron.metadata.docs\n",
        "from vultron.wire.as2.vocab.base.base import as_Base\n",
    ],
    ids=["renderer", "tutorial", "unrelated", "other-vultron", "sibling"],
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
    problems = rendering_problems(uses)
    assert not problems, (
        "These pages do not show the committed example. Name a committed "
        "example with a string literal, or re-run uv run python "
        "vultron/wire/as2/vocab/examples/vocab_examples.py and commit the "
        "result:\n  " + "\n  ".join(problems)
    )


@pytest.mark.parametrize(
    ("code", "names"),
    [
        ('render_example("case_status")', ["case_status"]),
        ("render_example(name)", [None]),
        ("render_example()", [None]),
        ('print(json2md(case_status()))\nlen("x")', []),
    ],
    ids=["literal", "variable", "no-argument", "other-calls"],
)
def test_rendered_names_reads_each_call(code, names):
    assert rendered_names(code) == names


def test_the_gate_reports_each_kind_of_problem(tmp_path):
    """Not-literal, unknown and drifted each fail, so a pass means something."""
    (tmp_path / "case_status.json").write_text("{}", encoding="utf-8")
    problems = rendering_problems(
        [("a.md:1", None), ("b.md:2", "no_such"), ("c.md:3", "case_status")],
        committed_dir=tmp_path,
    )
    assert len(problems) == 3
    assert "a.md:1" in problems[0] and "not a string literal" in problems[0]
    assert "b.md:2" in problems[1] and "'no_such'" in problems[1]
    assert problems[2].startswith("case_status:")


def test_the_gate_passes_a_committed_example():
    assert rendering_problems([("a.md:1", "case_status")]) == []


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
        check=False,
        # Under the unit tier's per-test ceiling, so a hang fails here with
        # the child's own message rather than as a bare ceiling trip.
        timeout=25,
    )
    assert result.returncode == 0, (
        f"the fresh process failed ({result.returncode}):\n{result.stderr}"
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
