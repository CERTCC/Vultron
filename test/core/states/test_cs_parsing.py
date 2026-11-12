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

"""The state-string parsers accept exactly the ``CS`` names (#6328).

They validate against the authoritative ``CS`` enum, not the legacy
``case_states.validations`` rules, and refuse a string that names no state
with the ``StateValidationError`` the legacy decorator raised.  The legacy
model is the oracle for which strings are states (ADR-0060).
"""

from itertools import product

import pytest

from vultron.core.case_states.validations import valid_states
from vultron.core.states.cs import parsing
from vultron.core.states.cs.states import CS
from vultron.errors import StateValidationError

_PARSERS = [
    parsing.vfd,
    parsing.pxa,
    parsing.state_string_to_enums,
    parsing.state_string_to_enum2,
]

#: Every upper/lower-case spelling of the six events, plus wildcard patterns.
_SPELLINGS = ["".join(p) for p in product("vV", "fF", "dD", "pP", "xX", "aA")]

_NOT_STATES = [
    "vFdpxa",  # fix ready before the vendor is aware
    "vfDpxa",  # fix deployed before it is ready
    "VfDPXA",
    "V.d...",  # a pattern, not a state
    "......",
    "vfdpx",  # too short
    "vfdpxaa",  # too long
    "xpdfva",  # events out of order
    "VFDPXa ",
    "",
    None,
    42,
    CS.vfdpxa,  # a member, not a state string
]


def test_cs_state_names_exactly_the_legacy_valid_states():
    accepted = set()
    for spelling in _SPELLINGS:
        try:
            parsing.cs_state(spelling)
        except StateValidationError:
            continue
        accepted.add(spelling)
    assert accepted == set(valid_states())


@pytest.mark.spec("CSB-17-001")
@pytest.mark.parametrize("member", list(CS), ids=lambda m: m.name)
def test_cs_state_returns_the_named_member(member):
    assert parsing.cs_state(member.name) is member


@pytest.mark.spec("CSB-17-001")
@pytest.mark.parametrize("parser", _PARSERS, ids=lambda f: f.__name__)
@pytest.mark.parametrize("bad", _NOT_STATES, ids=repr)
def test_every_parser_refuses_a_string_naming_no_state(parser, bad):
    with pytest.raises(StateValidationError):
        parser(bad)


@pytest.mark.parametrize("member", list(CS), ids=lambda m: m.name)
def test_state_string_to_enums_returns_the_members_parts(member):
    assert parsing.state_string_to_enums(member.name) == tuple(member.value)


@pytest.mark.parametrize("member", list(CS), ids=lambda m: m.name)
def test_vfd_returns_the_members_vf_and_d_parts(member):
    assert parsing.vfd(member.name) == (
        member.value.vf_state,
        member.value.d_state,
    )


@pytest.mark.parametrize("member", list(CS), ids=lambda m: m.name)
def test_pxa_returns_the_members_pxa_value(member):
    assert parsing.pxa(member.name) == member.value.pxa_state.value


@pytest.mark.parametrize("member", list(CS), ids=lambda m: m.name)
def test_state_string_to_enum2_spells_the_state(member):
    parts = parsing.state_string_to_enum2(member.name)
    assert "".join(str(p) for p in parts) == member.name
