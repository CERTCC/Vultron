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
"""Reading a callable's signature without evaluating its annotations.

Python 3.14 evaluates annotations lazily (PEP 649, PEP 749), so production
code writes a ``TYPE_CHECKING``-only name unquoted (``trigger_activity:
TriggerActivityPort | None``).  ``inspect.signature`` evaluates annotations
by default, and that name is not defined at runtime, so it raises
``NameError``.  A test that asks which parameters a callable takes, or what
their defaults are, reads the signature here instead: each annotation that
resolves is the real object, and each one that does not is an
``annotationlib.ForwardRef``.
"""

import annotationlib
import inspect
from collections.abc import Callable
from typing import Any


def signature_of(obj: Callable[..., Any]) -> inspect.Signature:
    """Return *obj*'s signature, with unresolvable annotations as
    ``annotationlib.ForwardRef`` instead of a ``NameError``."""
    return inspect.signature(
        obj, annotation_format=annotationlib.Format.FORWARDREF
    )


__all__ = ["signature_of"]
