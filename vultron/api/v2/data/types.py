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

# Copyright

"""
Provides Object Types for Vultron API v2 Data Layer.
"""


class UniqueKeyDict(dict):
    """
    A dictionary subclass that raises a KeyError if an attempt is
    made to set a key that already exists, thus preventing key overwriting.
    """

    def __setitem__(self, key, value):
        """
        Overrides the standard dict behavior for d[key] = value.
        Checks for existing keys before assignment.
        """
        if key in self:
            # If it exists, raise an exception
            raise KeyError(
                f"Key '{key}' already exists. Duplicate keys are not allowed."
            )

        # If the key is new, call the parent dict's __setitem__ to perform the assignment
        super().__setitem__(key, value)

    def update_value(self, key, new_value):
        """
        Allows updating the value associated with an EXISTING key.
        """
        # Check if the key exists before updating
        if key not in self:
            # Raise an error if the key doesn't exist (it should be set using d[key] = value first)
            raise KeyError(
                f"Key '{key}' not found. Cannot update a non-existent key."
            )

        # Call the parent dict's __setitem__ to perform the update
        super().__setitem__(key, new_value)
