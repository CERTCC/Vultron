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

"""Reading a class's own annotations while the class is being built."""

import annotationlib
from typing import Any


def own_annotations(owner: object) -> dict[str, Any]:
    """Return the annotations *owner* (a class or a function) itself
    declares, without failing on a name that is not defined yet.

    Python 3.14 evaluates annotations lazily (PEP 649, PEP 749), so an
    unquoted forward reference is legal in a class body.  Reading the
    annotations with the default ``VALUE`` format evaluates them, and inside
    ``__init_subclass__`` a name defined later in the module (``replies:
    CoreObjectOrIri | None``) raises ``NameError``.  The ``FORWARDREF``
    format returns the value of each annotation that resolves and an
    ``annotationlib.ForwardRef`` for each one that does not yet, so a
    membership test (``"type_" in own_annotations(cls)``) never fails and a
    resolvable annotation (``Literal["Note"]``) is the real object.
    """
    return annotationlib.get_annotations(
        owner, format=annotationlib.Format.FORWARDREF
    )


__all__ = ["own_annotations"]
