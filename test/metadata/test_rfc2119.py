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
"""Tests for :mod:`vultron.metadata.rfc2119`, the shared keyword reader.

Specs: MS-03-001, DF-12-004.
"""

from __future__ import annotations

import pytest

from vultron.metadata.rfc2119 import keywords_in, strip_code_spans


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("A participant MUST send it.", ["MUST"]),
        ("It MUST NOT send it.", ["MUST"]),
        ("It is NOT RECOMMENDED.", ["RECOMMENDED"]),
        ("It SHOULD send it and MAY log it.", ["SHOULD", "MAY"]),
        ("It must send it.", []),
        ("It MUST name `SHOULD` as a value.", ["MUST"]),
        ("It MUST name ``a `MAY` b`` as a value.", ["MUST"]),
    ],
)
def test_keywords_in(text, expected):
    assert keywords_in(text) == expected


def test_strip_code_spans_replaces_each_span():
    assert strip_code_spans("a `b` c `d e` f", "x") == "a x c x f"
