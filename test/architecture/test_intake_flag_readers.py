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

"""Only the handling tree reads intake's in-memory lists (CLP-10-073).

A received message moves through stages -- arrival, the doors, waiting, the
handling tree, the outcome -- and each one reads the record and the store, not
what an earlier stage happened to leave in memory (ADR-0154).  The handling
tree is the one exception: it is a single unit with one blackboard, so its own
nodes may read each other (ADR-0135).

``IntakeReceivedActivityNode`` publishes two such lists, ``stored_ids`` and
``found_ids``, and the property ``stored_anything`` over them.  They say
whether *this* delivery was new, which is exactly the kind of fact a later
stage must not take on trust: the outcome stage decides the record's final
stage from the handler's verdict (CLP-10-073), and the seen-before answer
comes from the record, not from intake.

So this pins the readers to an exact allow-list, every one of them inside the
handling tree.  It is not a ratchet to zero: the handling tree's own readers
are legitimate, and the list is meant to stay non-empty.  It bites when a new
stage, in the inbox pipeline or elsewhere, reaches for one of them.
"""

import ast

import pytest

from test.architecture import _corpus
from vultron.metadata.ratchet_markers import is_ratchet_name

#: The intake node's in-memory lists, and the property over them.
_INTAKE_FLAGS = frozenset({"stored_ids", "found_ids", "stored_anything"})

#: The module that owns the flags, which declares rather than reads them.
_INTAKE_MODULE = "vultron/core/behaviors/case/nodes/intake.py"

#: Modules allowed to read an intake flag, and why each is inside the
#: handling tree.  An exact allow-list, not a ratchet to zero.
# permanent: ADR-0154
INTAKE_FLAG_READER_EXEMPTIONS: dict[str, str] = {
    # The tree's own verdict: intake-only trees report APPLIED for a new
    # arrival and SKIPPED for one already held (HP-01-003).
    "vultron/core/use_cases/received/_bt_verdict/verdict.py": (
        "the handling tree's own verdict for an intake-only tree (HP-01-003)"
    ),
    # Both inside one received tree: the refusal effects and the
    # ledger-position answer are skipped on a redelivery (CLP-10-044,
    # SYNC-18-002).  The seen-before door, #5045's third part, retires both
    # readings.
    "vultron/core/behaviors/case/nodes/refusal_stage.py": (
        "a redelivery's refusal effects are skipped in the same tree"
        " (CLP-10-044)"
    ),
    "vultron/core/behaviors/case/receive_stages/decisions.py": (
        "a redelivery's ledger position is not answered again, in the same"
        " tree (SYNC-18-002)"
    ),
}


def _reads_an_intake_flag(tree: ast.AST) -> set[str]:
    """Every intake flag *tree* reads off another object.

    An attribute load, not a store: ``node.found_ids`` read somewhere else is
    a stage trusting intake's memory, while ``self.found_ids = []`` inside the
    node is the node keeping its own.  A flag named as ``getattr``'s
    attribute is the same read spelled another way, so it counts too.
    """
    reads: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr in _INTAKE_FLAGS
            and isinstance(node.ctx, ast.Load)
        ):
            reads.add(node.attr)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in _INTAKE_FLAGS
        ):
            reads.add(str(node.args[1].value))
    return reads


@pytest.mark.spec("ARCH-18-003")
def test_the_exemption_list_is_named_as_the_parser_expects():
    """Else the owner check passes blind over it (ARCH-18-003, #5535)."""
    assert is_ratchet_name("INTAKE_FLAG_READER_EXEMPTIONS")


@pytest.mark.spec("CLP-10-073")
def test_only_the_handling_tree_reads_an_intake_flag():
    offenders: dict[str, set[str]] = {}
    seen_any = False
    for path, tree in _corpus.files_mentioning(
        *_INTAKE_FLAGS, under=_corpus.REPO_ROOT / "vultron"
    ):
        relative = str(path.relative_to(_corpus.REPO_ROOT))
        if relative == _INTAKE_MODULE:
            continue
        flags = _reads_an_intake_flag(tree)
        if flags:
            seen_any = True
        if flags and relative not in INTAKE_FLAG_READER_EXEMPTIONS:
            offenders[relative] = flags

    # Guard against a silently empty scan: a rename of a flag, or a corpus
    # helper that stops matching, would otherwise read as a clean pass.
    assert seen_any, (
        "no module in vultron/ reads an intake flag — the scan found nothing,"
        " so this check is not testing anything (has a flag been renamed?)"
    )
    assert offenders == {}, (
        "these modules read the intake node's in-memory state from outside"
        " the handling tree; read the record instead, or the handler's"
        f" verdict (CLP-10-073, ADR-0154): {offenders}"
    )


@pytest.mark.spec("CLP-10-073")
def test_every_exempt_module_still_reads_one():
    """A stale exemption is a claim nothing backs; drop it when it is empty."""
    for relative in INTAKE_FLAG_READER_EXEMPTIONS:
        path = _corpus.REPO_ROOT / relative
        assert path.is_file(), f"{relative} no longer exists"
        tree = _corpus.parse_inline(path.read_text(encoding="utf-8"))
        assert _reads_an_intake_flag(tree), (
            f"{relative} reads no intake flag any more; remove its exemption"
        )


@pytest.mark.spec("CLP-10-073")
def test_the_outcome_stage_reads_no_intake_flag():
    """The one stage this slice adds, named so the check cannot go vacuous.

    It decides the final stage from the handler's verdict alone, published by
    ``DispatchNode`` (UCORG-05-010), so it reads nothing intake left behind.
    """
    stage = (
        _corpus.REPO_ROOT
        / "vultron/core/behaviors/inbox/nodes/outcome_stage.py"
    )
    assert stage.is_file()
    tree = _corpus.parse_inline(stage.read_text(encoding="utf-8"))
    assert _reads_an_intake_flag(tree) == set()
