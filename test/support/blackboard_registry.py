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

"""Read what py_trees' process-global client registry holds (#6727).

``py_trees.blackboard.Blackboard`` keeps two process-global maps besides
``storage``: ``clients`` (one entry per registered ``Client``) and ``metadata``
(each key's reader, writer and exclusive client ids).  Neither entry is
dropped when its ``Client`` object is collected, so a tree run that does not
release its clients leaves them for the life of the process.  A demo test
built about 5,000 clients per test this way, which is what grew a loaded
worker until the kernel killed it (#6727).
"""

import uuid
from dataclasses import dataclass

import py_trees


@dataclass(frozen=True)
class RegistrySnapshot:
    """The client ids the registry holds, and every id a key's metadata names."""

    clients: frozenset[uuid.UUID]
    metadata_ids: frozenset[tuple[str, str, uuid.UUID]]

    def gained_since(self, earlier: RegistrySnapshot) -> RegistrySnapshot:
        """What this snapshot holds that *earlier* did not."""
        return RegistrySnapshot(
            clients=self.clients - earlier.clients,
            metadata_ids=self.metadata_ids - earlier.metadata_ids,
        )

    def __bool__(self) -> bool:
        return bool(self.clients or self.metadata_ids)

    def describe(self) -> str:
        """Name the clients and keys, for an assertion message."""
        names = sorted(
            {
                py_trees.blackboard.Blackboard.clients.get(uid, str(uid))
                for uid in self.clients
            }
        )
        keys = sorted({key for key, _access, _uid in self.metadata_ids})
        return (
            f"{len(self.clients)} client(s) {names[:10]}, "
            f"{len(self.metadata_ids)} key registration(s) on {keys[:10]}"
        )


def registry_snapshot() -> RegistrySnapshot:
    """The registry's current client ids and key registrations."""
    board = py_trees.blackboard.Blackboard
    return RegistrySnapshot(
        clients=frozenset(board.clients),
        metadata_ids=frozenset(
            (key, access, uid)
            for key, meta in board.metadata.items()
            for access, ids in (
                ("read", meta.read),
                ("write", meta.write),
                ("exclusive", meta.exclusive),
            )
            for uid in ids
        ),
    )
