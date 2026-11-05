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

"""One module owns the holding transitions of a received record (ADR-0154).

``ReceivedActivityRecord`` carries two independent facts -- how far the
message got (``stage``) and whether a replay is still owed (``replay_owed``,
with ``awaiting_case_id``).  Three of their four pairings are legitimate, and
getting a transition wrong loses a message or deletes an archive a refusal
must leave standing (CLP-10-018).  Keeping every transition in
``received_holding.py`` is what makes that reviewable in one place, so this
pins that no other module sets those fields.

The exception is intake, which states the stage it archives at as a
constructor argument.  Naming it is the point: a reader of the node sees
which stage intake writes without going to the service.

The model itself needs no exemption: it *declares* the fields and reads them
in its invariant, and declaring is not setting.

**Why ``stage`` is not policed by name.** ``stage`` is a word this codebase
uses for the received tree's door stages too, so an assignment to something
called ``stage`` is no evidence about this record (``CheckReceivedPathNode``
stores its path stage that way).  Policing the two replay fields is enough:
the harm this guards against -- a lost message, or an archive deleted with
the hold it carried -- needs one of them, and a lone ``stage`` write that
broke the pairing is refused by the record's own invariant, which
``test/core/models/test_received_activity_record.py`` covers.
"""

import ast

import pytest

from test.architecture import _corpus
from vultron.metadata.ratchet_markers import is_ratchet_name

#: The holding fields no module outside the sanctioned writers may set.
#: ``stage`` is deliberately absent -- see the module docstring.
_HOLDING_FIELDS = frozenset({"replay_owed", "awaiting_case_id"})

#: Modules allowed to set a holding field, and why.  An exact allow-list, not
#: a ratchet to zero: these are the sanctioned writers, and the list is meant
#: to stay non-empty.
# permanent: ADR-0154
HOLDING_FIELD_WRITER_EXEMPTIONS: dict[str, str] = {
    # The one place the three legitimate pairings are kept straight.
    "vultron/core/services/received_holding.py": (
        "owns every holding transition (ADR-0154)"
    ),
    # States the stage and flag it archives at, so the node reads for itself.
    "vultron/core/behaviors/case/nodes/intake.py": (
        "names the stage intake archives at (CLP-10-017)"
    ),
}


def _sets_a_holding_field(tree: ast.AST) -> set[str]:
    """Every holding field *tree* writes onto a record.

    Three shapes write one, and nothing else does:

    - ``ReceivedActivityRecord(replay_owed=...)`` -- construction;
    - ``record.replay_owed = ...`` -- assignment;
    - ``record.model_copy(update={"replay_owed": ...})`` -- the Pydantic copy.

    Passing ``awaiting_case_id=`` *to* the holding service is not a write: it
    asks the service to make one.  Counting it would flag every caller and
    make the allow-list meaningless.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            found |= _fields_a_call_writes(node)
        elif isinstance(node, ast.Assign):
            found |= {
                target.attr
                for target in node.targets
                if isinstance(target, ast.Attribute)
                and target.attr in _HOLDING_FIELDS
            }
    return found


def _called_name(call: ast.Call) -> str | None:
    """The bare name of what *call* calls, attribute or plain."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _fields_a_call_writes(call: ast.Call) -> set[str]:
    """The holding fields *call* writes, for the two writing call shapes."""
    name = _called_name(call)
    if name == "ReceivedActivityRecord":
        return {
            keyword.arg
            for keyword in call.keywords
            if keyword.arg in _HOLDING_FIELDS
        }
    if name != "model_copy":
        return set()
    found: set[str] = set()
    for keyword in call.keywords:
        if keyword.arg == "update" and isinstance(keyword.value, ast.Dict):
            found |= {
                str(key.value)
                for key in keyword.value.keys
                if isinstance(key, ast.Constant)
                and key.value in _HOLDING_FIELDS
            }
    return found


@pytest.mark.spec("ARCH-18-003")
def test_the_exemption_list_is_named_as_the_parser_expects():
    """Else the owner check passes blind over it (ARCH-18-003, #5535)."""
    assert is_ratchet_name("HOLDING_FIELD_WRITER_EXEMPTIONS")


@pytest.mark.spec("IO-03-009")
def test_only_the_sanctioned_writers_set_a_holding_field():
    offenders: dict[str, set[str]] = {}
    seen_any = False
    for path, tree in _corpus.files_mentioning(
        *_HOLDING_FIELDS,
        "ReceivedActivityRecord",
        under=_corpus.REPO_ROOT / "vultron",
    ):
        relative = str(path.relative_to(_corpus.REPO_ROOT))
        fields = _sets_a_holding_field(tree)
        if fields:
            seen_any = True
        if fields and relative not in HOLDING_FIELD_WRITER_EXEMPTIONS:
            offenders[relative] = fields

    # Guard against a silently empty scan: a rename of the field, or a corpus
    # helper that stops matching, would otherwise read as a clean pass.
    assert seen_any, (
        "no module in vultron/ sets a holding field — the scan found nothing,"
        " so this ratchet is not testing anything (has a field been renamed?)"
    )
    assert offenders == {}, (
        "these modules set a holding field without being a sanctioned writer;"
        " route the transition through"
        f" vultron/core/services/received_holding.py: {offenders}"
    )


@pytest.mark.spec("IO-03-009")
def test_every_sanctioned_writer_still_sets_one():
    """A stale exemption is a claim nothing backs; drop it when it is empty."""
    for relative in HOLDING_FIELD_WRITER_EXEMPTIONS:
        path = _corpus.REPO_ROOT / relative
        assert path.is_file(), f"{relative} no longer exists"
        tree = _corpus.parse_inline(path.read_text(encoding="utf-8"))
        assert _sets_a_holding_field(tree), (
            f"{relative} sets no holding field any more; remove its exemption"
        )
