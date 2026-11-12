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
"""``own_annotations`` reads a class's annotations without evaluating a
forward reference the module has not defined yet (PEP 649, #6054)."""

import annotationlib
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from vultron.core.models._helpers import own_annotations

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort


class _Recorder:
    """Reads each subclass's annotations while the class is being built, as
    the ``CoreObject`` and ``as_Base`` registration hooks do."""

    seen: ClassVar[dict[str, dict[str, Any]]] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__()
        _Recorder.seen[cls.__name__] = own_annotations(cls)


class _Early(_Recorder):
    later: DefinedLater | None = None


class DefinedLater:
    """Defined after ``_Early`` names it, as ``CoreObjectOrIri`` is after
    ``CoreObject``."""


def test_a_name_defined_later_reads_as_a_forward_ref_at_class_creation() -> (
    None
):
    annotations = _Recorder.seen["_Early"]

    assert "later" in annotations
    assert isinstance(annotations["later"], annotationlib.ForwardRef)


def test_a_resolvable_annotation_is_the_real_object() -> None:
    class Note:
        type_: Literal["Note"] = "Note"

    assert own_annotations(Note) == {"type_": Literal["Note"]}


def test_an_inherited_annotation_is_not_the_class_own() -> None:
    class Base:
        type_: str = "Base"

    class Child(Base):
        name: str = ""

    assert own_annotations(Child) == {"name": str}


def test_a_type_checking_name_in_a_function_reads_as_a_forward_ref() -> None:
    def factory(port: TriggerActivityPort) -> None:
        return None

    annotations = own_annotations(factory)

    assert isinstance(annotations["port"], annotationlib.ForwardRef)
    assert annotations["return"] is None
