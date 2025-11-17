#!/usr/bin/env python

#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
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
"""
Provides an in-memory data layer for testing and development.
"""
import logging
from typing import Protocol

from vultron.api.v2.data.types import UniqueKeyDict
from vultron.as_vocab.base.base import as_Base
from vultron.as_vocab.base.registry import find_in_vocabulary

logger = logging.getLogger(__name__)

_STORE: dict[str, as_Base] = UniqueKeyDict()


class KeyValueStore(Protocol):
    """Protocol for a simple key-value store."""

    def create(self, obj: as_Base) -> None: ...

    def read(self, object_id: str) -> dict | None: ...

    def update(self, object_id: str, obj: dict) -> None: ...

    def delete(self, object_id: str) -> None: ...

    def all(self) -> dict[str, dict]: ...


class DataStore(KeyValueStore):
    """A simple in-memory data store for Vultron objects."""

    def __contains__(self, key):
        return key in _STORE

    def create(self, obj: as_Base) -> None:

        if not hasattr(obj, "as_id"):
            raise ValueError("Object must have an 'as_id' field")

        obj_id = obj.as_id

        # just get the part after the last slash to use as key
        # FRAGILE: This assumes that IDs are URLs, and that the last part is globally unique
        # (which will not always be true, but in our demo here we are using UUIDs so it's okay)
        obj_id = obj_id.rsplit("/", 1)[-1]

        logger.debug(
            f"Creating object\n\t'{obj_id}': {obj.model_dump_json(indent=2,exclude_none=True)}"
        )

        # This will raise a KeyError if the key already exists
        _STORE[obj_id] = obj

    def read(self, object_id: str, raise_on_missing=False) -> as_Base | None:
        """
        Reads an object from the store.
        Args:
            object_id: The ID of the object to read.
            raise_on_missing: If True, raises a KeyError if the object is not found.

        Returns:
            The object, or None if not found and raise_on_missing is False.
        """
        obj = _STORE.get(object_id)

        if obj is None and raise_on_missing:
            raise KeyError(f"Object with ID '{object_id}' not found in store.")

        return obj

    def update(self, object_id: str, obj: dict) -> None:
        """
        Updates an existing object in the store.

        Args:
            object_id: The ID of the object to update.
            obj: The new object data as a dictionary.

        Returns:
            None

        Raises:
            KeyError: If the object with the given ID does not exist.
        """

        old_obj = _STORE[object_id]
        old_obj_dict = old_obj.model_dump()
        old_obj_dict.update(obj)
        updated_obj = old_obj.model_validate(old_obj_dict)
        _STORE.update_value(object_id, updated_obj)

    def delete(self, object_id: str) -> None:
        """
        Deletes an object from the store.

        Args:
            object_id: The ID of the object to delete.

        Returns:
            None

        Raises:
            KeyError: If the object with the given ID does not exist.
        """
        del _STORE[object_id]

    def all(self) -> dict[str, dict]:
        return _STORE.copy()

    def by_type(self, as_type: str) -> dict[str, as_Base]:

        # find class in vocabulary
        cls = find_in_vocabulary(as_type)
        if cls is None:
            raise ValueError(f"Unknown type: {as_type}")

        results = {k: v for k, v in _STORE.items() if isinstance(v, cls)}

        return results

    def clear(self):
        _STORE.clear()


def get_datalayer() -> DataStore:
    return DataStore()
