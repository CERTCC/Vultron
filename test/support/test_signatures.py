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
"""``signature_of`` reads a signature whose annotations name a
``TYPE_CHECKING``-only import without raising (PEP 649, #6054)."""

import annotationlib
import inspect
from typing import TYPE_CHECKING

import pytest

from test.support.signatures import signature_of

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort


def _takes_a_port(port: TriggerActivityPort, retries: int = 3) -> None:
    return None


def test_inspect_signature_raises_on_a_type_checking_name() -> None:
    with pytest.raises(NameError, match="TriggerActivityPort"):
        inspect.signature(_takes_a_port)


def test_signature_of_names_every_parameter_and_default() -> None:
    signature = signature_of(_takes_a_port)

    assert list(signature.parameters) == ["port", "retries"]
    assert signature.parameters["retries"].default == 3
    assert signature.parameters["retries"].annotation is int
    assert isinstance(
        signature.parameters["port"].annotation, annotationlib.ForwardRef
    )
