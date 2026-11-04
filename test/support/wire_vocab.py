"""Fill the wire vocabulary registries before a test iterates them.

Registration is a submodule import side effect (VM-01-005), so a bare
``from ... import VOCABULARY`` yields only what earlier imports defined. The
wire sibling of :func:`test.support.core_vocab.import_all_core_models`.
"""

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

import importlib
import pkgutil


def import_all_wire_vocab() -> None:
    """Import every module under ``vultron.wire.as2.vocab`` so registries fill."""
    import vultron.wire.as2.vocab as vocab_pkg

    for module in pkgutil.walk_packages(
        vocab_pkg.__path__, vocab_pkg.__name__ + "."
    ):
        importlib.import_module(module.name)
