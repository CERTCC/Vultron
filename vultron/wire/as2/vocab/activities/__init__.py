#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import importlib
import pkgutil
import sys


def _discover_modules() -> None:
    """Import all modules in this package to ensure vocab classes are registered."""
    package = sys.modules[__name__]
    for _finder, name, _ispkg in pkgutil.iter_modules(
        package.__path__,  # type: ignore[attr-defined]
        package.__name__ + ".",
    ):
        if name not in sys.modules:
            importlib.import_module(name)


_discover_modules()
