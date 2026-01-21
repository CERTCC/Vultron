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
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

# Copyright

"""
Provides a Record model for document database storage.
"""
from pydantic import BaseModel


class Record(BaseModel):
    """Record wrapper stored in TinyDB.
    Internally fields are `id_`, `type_`, and `data_`.
    `type_` is intended to hold the class name of the stored object, and will used to select
    both the table name and the class to reconstitute the object when reading.
    `data_` holds the actual data of the object as a dict.
    """

    id_: str
    type_: str
    data_: dict


def object_to_record(obj: BaseModel) -> Record:
    """Converts a Pydantic BaseModel object to a Record for storage.

    Args:
        obj (BaseModel): The object to convert.
    Returns:
        Record: The converted Record.
    """
    if not isinstance(obj, BaseModel):
        raise ValueError(
            "Object must be a Pydantic BaseModel for Record conversion"
        )

    if not hasattr(obj, "as_id"):
        raise ValueError(
            "Object must have an 'as_id' attribute for Record conversion"
        )

    if not hasattr(obj, "as_type"):
        raise ValueError(
            "Object must have an 'as_type' attribute for Record conversion"
        )

    record = Record(
        id_=obj.as_id,
        type_=obj.as_type,
        data_=obj.model_dump(),
    )
    return record


def main():
    pass


if __name__ == "__main__":
    main()
