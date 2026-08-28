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
"""Architecture boundary test: wire layer must not introduce new direct imports of core models.

``vultron/wire/`` converts core domain objects to ActivityStreams 2.0 wire
format.  Translation MUST go through the explicit ``as_Foo.from_core(core_obj)``
seam on each wire vocab class — not through arbitrary direct imports of
``vultron.core.models.*`` types scattered across wire modules.

Spec: ARCH-22-001, ARCH-22-002, ARCH-22-003

Ratchet pattern
---------------
``KNOWN_VIOLATIONS`` enumerates every current direct ``vultron.core.models``
import in ``vultron/wire/``.  Two tests enforce opposite sides of the ratchet::

    test_no_new_wire_core_model_imports   — fails when the set *grows*
    test_all_known_violations_still_present — fails when a violation is *resolved*
                                              without being removed from the set

This means:

* **Adding a new violation** causes ``test_no_new_wire_core_model_imports`` to
  fail immediately.
* **Fixing a violation** also causes ``test_all_known_violations_still_present``
  to fail until the resolved entry is removed from ``KNOWN_VIOLATIONS``.

Remove entries from ``KNOWN_VIOLATIONS`` one by one as each violation is fixed.
When the set is empty, the companion goal test (``test_wire_core_model_import_boundary_goal``)
will XPASS and force deletion of its ``xfail`` marker, signalling completion
(ARCH-22-003).
"""

import ast

import pytest

from test.architecture import _corpus

_CORE_MODELS_MODULE = "vultron.core.models"

_WIRE_ROOT = _corpus.REPO_ROOT / "vultron" / "wire"


def _imports_core_models(tree: ast.AST) -> bool:
    """Return True if *tree* contains any direct import from vultron.core.models.

    Detects both top-level and deferred (local) imports, catching violations
    like ``from vultron.core.models.case import VulnerabilityCase`` placed
    inside a function body.
    """
    _prefix = _CORE_MODELS_MODULE + "."
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == _CORE_MODELS_MODULE or module.startswith(_prefix):
                return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _CORE_MODELS_MODULE or alias.name.startswith(
                    _prefix
                ):
                    return True
    return False


def _collect_violations() -> frozenset[str]:
    """Return repo-relative paths of wire files that import from vultron.core.models."""
    return frozenset(
        py_file.relative_to(_corpus.REPO_ROOT).as_posix()
        for py_file, tree in _corpus.files_mentioning(
            _CORE_MODELS_MODULE, under=_WIRE_ROOT
        )
        if _imports_core_models(tree)
    )


# Computed once at import time; both ratchet tests share this result.
_VIOLATIONS: frozenset[str] = _collect_violations()


# ---------------------------------------------------------------------------
# Known pre-existing violations awaiting migration to the from_core() seam.
# Remove an entry from this set when the violation is resolved.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: frozenset[str] = frozenset(
    {
        "vultron/wire/as2/enums.py",
        "vultron/wire/as2/extractor/_builders.py",
        "vultron/wire/as2/extractor/_extract.py",
        "vultron/wire/as2/extractor/_instances.py",
        "vultron/wire/as2/extractor/_pattern.py",
        "vultron/wire/as2/factories/actor.py",
        "vultron/wire/as2/factories/case.py",
        "vultron/wire/as2/vocab/activities/actor.py",
        "vultron/wire/as2/vocab/activities/base.py",
        "vultron/wire/as2/vocab/activities/case.py",
        "vultron/wire/as2/vocab/base/base.py",
        "vultron/wire/as2/vocab/base/objects/base.py",
        "vultron/wire/as2/vocab/base/registry.py",
        "vultron/wire/as2/vocab/objects/case_actor.py",
        "vultron/wire/as2/vocab/objects/case_ledger_entry.py",
        "vultron/wire/as2/vocab/objects/case_participant.py",
        "vultron/wire/as2/vocab/objects/case_participant_role.py",
        "vultron/wire/as2/vocab/objects/case_proposal.py",
        "vultron/wire/as2/vocab/objects/case_reference.py",
        "vultron/wire/as2/vocab/objects/case_status.py",
        "vultron/wire/as2/vocab/objects/embargo_event.py",
        "vultron/wire/as2/vocab/objects/embargo_policy.py",
        "vultron/wire/as2/vocab/objects/offer_record.py",
        "vultron/wire/as2/vocab/objects/pending_case_inbox.py",
        "vultron/wire/as2/vocab/objects/pending_create_case_activity.py",
        "vultron/wire/as2/vocab/objects/replication_state.py",
        "vultron/wire/as2/vocab/objects/report_case_link.py",
        "vultron/wire/as2/vocab/objects/vulnerability_case.py",
        "vultron/wire/as2/vocab/objects/vulnerability_record.py",
        "vultron/wire/as2/vocab/objects/vulnerability_report.py",
        "vultron/wire/as2/vocab/objects/vultron_actor.py",
    }
)


@pytest.mark.spec("ARCH-22-001")
def test_no_new_wire_core_model_imports() -> None:
    """No wire module may add a new direct import of vultron.core.models.

    Spec: ARCH-22-001, ARCH-22-002

    New wire→core model imports must go through the ``as_Foo.from_core()``
    translation seam instead.  See module docstring for the ratchet strategy.
    """
    new_violations = _VIOLATIONS - KNOWN_VIOLATIONS

    assert not new_violations, (
        "NEW wire→core model imports detected (ARCH-22-001):\n"
        + "\n".join(f"  + {v}" for v in sorted(new_violations))
        + "\n\nUse ``as_Foo.from_core(core_obj)`` instead of importing core types directly.\n"
        "Add to KNOWN_VIOLATIONS only if the import cannot yet be removed."
    )


@pytest.mark.spec("ARCH-22-002")
def test_all_known_violations_still_present() -> None:
    """All KNOWN_VIOLATIONS entries still exist — remove resolved ones from the set.

    Spec: ARCH-22-002

    When a wire→core model import is removed, the corresponding entry MUST be
    deleted from ``KNOWN_VIOLATIONS``.  Leaving stale entries masks future
    regressions.  See module docstring for the ratchet strategy.
    """
    resolved = KNOWN_VIOLATIONS - _VIOLATIONS

    assert not resolved, (
        "RESOLVED violations still listed in KNOWN_VIOLATIONS (remove them):\n"
        + "\n".join(f"  - {v}" for v in sorted(resolved))
    )


@pytest.mark.spec("ARCH-22-003")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "ARCH-22-003: Goal state — all wire→core model import violations resolved. "
        "Tracked by #2670. When the last actual wire→core model import is removed "
        "from the codebase, _VIOLATIONS becomes frozenset() and this test XPASSes, "
        "failing the build — delete this xfail marker and clear KNOWN_VIOLATIONS then."
    ),
)
def test_wire_core_model_import_boundary_goal() -> None:
    """Goal: wire layer has zero direct vultron.core.models imports.

    Spec: ARCH-22-003

    This test is ``xfail(strict=True)`` while any wire module still imports
    ``vultron.core.models``.  Once every actual violation is resolved,
    ``_VIOLATIONS`` becomes ``frozenset()`` and the test XPASSes, which causes
    a strict-xfail CI failure and forces deletion of this marker.
    """
    assert _VIOLATIONS == frozenset()
