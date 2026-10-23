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
"""The case event symbols carry hover tips that agree with the event legend.

``docs/javascripts/mathjax.js`` defines one MathJax macro per case event (for
example ``\\evF``), which renders the event's bold letter with a ``\\texttip``.
Each tip begins with the event's short name. The short names are owned by the
event legend (``_case_events.md``) and, for the split events, by the split table
on the desiderata page. These tests keep the three in step, fail on a macro a
page uses but nothing defines, and keep the pages that adopted the macros from
falling back to bare ``\\mathbf`` event letters.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from vultron.metadata.base import repo_root

DOCS = repo_root() / "docs"
MATHJAX = DOCS / "javascripts" / "mathjax.js"
LEGEND = DOCS / "topics" / "measuring_cvd" / "_case_events.md"
SPLITS = DOCS / "topics" / "measuring_cvd" / "process_model_desiderata.md"

#: Pages and fragments that write case events with the macros.
ADOPTED = [
    DOCS / "topics" / "measuring_cvd" / "_case_events.md",
    DOCS / "topics" / "measuring_cvd" / "what_a_case_records.md",
    DOCS / "topics" / "measuring_cvd" / "process_model_desiderata.md",
    DOCS / "topics" / "measuring_cvd" / "timing_metrics.md",
    DOCS / "topics" / "measuring_cvd" / "open_questions.md",
    DOCS / "howto" / "measure_your_cvd_program.md",
    DOCS / "includes" / "twelve_desiderata.md",
]

_MACRO = re.compile(
    r'^\s*(?P<name>ev[A-Za-z]+):\s*\["\\\\texttip\{(?P<sym>.+?)\}\{(?P<tip>[^}]*)\}",\s*0\]',
    re.MULTILINE,
)
_LEGEND_ROW = re.compile(
    r"^\| \$\\(?P<name>ev[A-Za-z]+)(?:_\w)?\$ \| [^|]*\((?P<short>[^)]+)\) \|",
    re.M,
)
_SPLIT_ROW = re.compile(
    r"^\| (?P<short>[^|(]+?) \(\$\\(?P<name>ev[A-Za-z]+)\$\) \|", re.M
)
_USED = re.compile(r"\\(ev[A-Z][A-Za-z]*)")
_RAW_EVENT = re.compile(
    r"\\mathbf\{(?:R|Va|Ac|C|J|S|V|F|D|P|X|A|E|E_x[^}]*|P_u|P_\\ell)\}"
)


def _macros() -> dict[str, str]:
    found = {m["name"]: m["tip"] for m in _MACRO.finditer(MATHJAX.read_text())}
    assert found, f"no event macros found in {MATHJAX}"
    return found


def _short_names() -> dict[str, str]:
    names = {
        m["name"]: m["short"] for m in _LEGEND_ROW.finditer(LEGEND.read_text())
    }
    names.update(
        (m["name"], m["short"].lower())
        for m in _SPLIT_ROW.finditer(SPLITS.read_text())
    )
    assert names, "no event short names found in the legend or the split table"
    return names


def test_every_macro_has_a_short_name_and_every_short_name_a_macro():
    assert set(_macros()) == set(_short_names())


@pytest.mark.parametrize("name", sorted(_short_names()))
def test_tip_starts_with_the_events_short_name(name: str):
    tip = _macros()[name]
    assert tip.startswith(f"{_short_names()[name]}: "), (name, tip)


def test_every_macro_a_page_uses_is_defined():
    defined = set(_macros())
    undefined = {
        f"{path.relative_to(DOCS)}: \\{name}"
        for path in DOCS.rglob("*.md")
        for name in _USED.findall(path.read_text())
        if name not in defined
    }
    assert not undefined, sorted(undefined)


@pytest.mark.parametrize("path", ADOPTED, ids=lambda p: str(Path(p).name))
def test_adopted_pages_use_the_macros_not_bare_event_letters(path: Path):
    hits = _RAW_EVENT.findall(path.read_text())
    assert not hits, (
        f"{path.relative_to(DOCS)} writes {hits}; use the \\ev… macros"
    )
