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
"""Planned behaviour recorded by the 2026-10-02 audit (#4195).

Strict-``xfail`` tests for protocol requirements the audit added before the
code that satisfies them exists.  Each flips to passing once the issue named
in its reason lands; see ``notes/spec-authoring-rules.md`` § "Never Raise the
Ceiling — Use a Strict ``xfail``".
"""

import inspect
import pkgutil

import pytest

import vultron.core.ports as ports_pkg
from vultron.core.behaviors.case.nodes import close_case_effect


def _has_dereference_port() -> bool:
    return any(
        "dereference" in m.name
        for m in pkgutil.iter_modules(ports_pkg.__path__)
    )


@pytest.mark.spec("AKM-05-003")
@pytest.mark.xfail(
    strict=True,
    reason="AKM-05-003: no object-dereference port exists yet. #3258, #3739.",
)
def test_a_port_dereferences_an_actor_by_reference():
    assert _has_dereference_port()


@pytest.mark.spec("AKM-05-004")
@pytest.mark.xfail(
    strict=True,
    reason="AKM-05-004: production needs object dereference by API call. #3258, #3739.",
)
def test_production_dereferences_an_object_by_api_call():
    assert _has_dereference_port()


@pytest.mark.spec("CM-23-016")
@pytest.mark.xfail(
    strict=True,
    reason="CM-23-016: the close-case fan-out still walks the RM table. Tracked by #4210 (source #4091).",
)
def test_replica_closure_does_not_re_derive_rungs_from_the_rm_table():
    assert "RMClosureWriter" not in inspect.getsource(close_case_effect)
