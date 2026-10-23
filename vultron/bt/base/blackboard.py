#!/usr/bin/env python
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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
This module defines Blackboard class for sharing data between nodes in the tree.

The default Blackboard class is a dict, which is good enough if you just want
to run a single tree in a single process.

If you want multiple trees in a single process with shared state, just use
the same Blackboard object instance for each tree.

If you want to run multiple trees in a single process without shared state,
you'll need to use a different Blackboard object instance for each tree.
You can still do that with the default Blackboard class, but you'll need to
create a new Blackboard object instance for each tree.

If you want to run multiple trees in multiple processes with shared state,
you'll need to use a Blackboard object that can communicate with some external
data store, such as a key-value store on a server. The default Blackboard
class is not designed for that use case, but you can subclass it to use
any object that implements the `__getitem__` and `__setitem__` methods
to provide a python dict-like interface.
For example, mongodict and redis-dict provide such an interface for MongoDb and Redis,
respectively.
"""


class Blackboard(dict):
    """
    Provides a blackboard object for sharing data between nodes in the tree.
    To use a custom blackboard object, subclass this class and set
    the BehaviorTree's bbclass attribute to your subclass.
    """
