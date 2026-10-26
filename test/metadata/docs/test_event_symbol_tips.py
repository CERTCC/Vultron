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
Each tip reads "<short name>: <meaning>". The event legend
(``_case_events.md``) owns both halves for its events; the split table on the
desiderata page owns the short names of the split events and must agree with the
legend wherever the two overlap. These tests keep them in step, fail on a macro a
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
    DOCS / "topics" / "background" / "cvd_success.md",
]

_MACRO = re.compile(
    r'^\s*(?P<name>ev[A-Za-z]+):\s*\["\\\\texttip\{(?P<sym>.+?)\}\{(?P<tip>[^}]*)\}",\s*0\]',
    re.MULTILINE,
)
_LEGEND_ROW = re.compile(
    r"^\| \$\\(?P<name>ev[A-Za-z]+)(?:_\w)?\$ \| (?P<event>[^|(]+?) \((?P<short>[^)]+)\) \|",
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


#: How the legend names a subscripted owner, and how a tip names it.
_OWNERS = {
    "Participant $i$": "a participant",
    "Vendor $i$": "a vendor",
    "Deployer $k$": "a deployer",
}


def _legend_rows() -> dict[str, tuple[str, str]]:
    """Map each legend macro to its (short name, meaning as a tip writes it)."""
    rows = {}
    for m in _LEGEND_ROW.finditer(LEGEND.read_text()):
        event = m["event"]
        for owner, generic in _OWNERS.items():
            event = event.replace(owner, generic)
        rows[m["name"]] = (m["short"], event[0].lower() + event[1:])
    assert rows, f"no event rows found in {LEGEND}"
    return rows


def _split_names() -> dict[str, str]:
    names = {
        m["name"]: m["short"].lower()
        for m in _SPLIT_ROW.finditer(SPLITS.read_text())
    }
    assert names, f"no split-table rows found in {SPLITS}"
    return names


def _short_names() -> dict[str, str]:
    # The legend owns its events' names; the split table only adds new ones.
    legend = {name: short for name, (short, _) in _legend_rows().items()}
    return {**_split_names(), **legend}


def test_split_table_agrees_with_the_legend_where_they_overlap():
    legend = _short_names()
    disagree = {
        name: (short, legend[name])
        for name, short in _split_names().items()
        if name in _legend_rows() and short != legend[name]
    }
    assert not disagree, disagree


def test_every_macro_has_a_short_name_and_every_short_name_a_macro():
    assert set(_macros()) == set(_short_names())


@pytest.mark.parametrize("name", sorted(_short_names()))
def test_tip_starts_with_the_events_short_name(name: str):
    tip = _macros()[name]
    assert tip.startswith(f"{_short_names()[name]}: "), (name, tip)


@pytest.mark.parametrize("name", sorted(_legend_rows()))
def test_legend_event_tip_matches_the_legend_row(name: str):
    short, meaning = _legend_rows()[name]
    assert _macros()[name] == f"{short}: {meaning}", name


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


def test_config_loads_the_action_extension_at_startup():
    # Autoload does not define \texttip in time for macros expanded from the
    # config, so in a browser every event symbol rendered as a red error.
    config = MATHJAX.read_text()
    assert '"[tex]/action"' in config, "loader.load must include [tex]/action"
    assert re.search(r'packages:\s*\{\s*"\[\+\]":\s*\["action"\]', config), (
        'tex.packages must add "action"'
    )
