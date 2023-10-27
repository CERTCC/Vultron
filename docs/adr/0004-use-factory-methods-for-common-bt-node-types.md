---
# These are optional elements. Feel free to remove any of them.
status: accepted
date: 2023-10-24
deciders: adh
---
# Use factory methods for common BT node types

## Context and Problem Statement

We have a number of common BT node types that are used in multiple trees.  We want to be able to create these nodes
in a consistent way, and we want to be able to easily change the implementation of these nodes without having to
change the code that creates them.

## Decision Drivers

* We want to be able to create these nodes in a consistent way
* Preserve future flexibility to change the underlying BT node implementation without having to change the code that creates them

## Considered Options

* No factory methods, directly subclass the BT node types
* Use factory methods

## Decision Outcome

Chosen option: "Use factory methods", because it allows us to create the nodes in a consistent way, and it allows us to
change the underlying implementation without having to change the code that creates them.

### Consequences

Good because:
* retains flexibility to change the underlying implementation without having to change the code that creates them
* allows us to create the nodes in a consistent way
* allows us to keep the `vultron.bt.base` module clean and focused on the base classes
* allows us to keep the rest of the `vultron.bt` module focused on Vultron-specific needs

Neutral because:
* Adds a central place to maintain the factory methods

Bad because:
* less pythonic than just subclassing the BT node types

## Pros and Cons of the Options

### No factory methods

Good because:

* more pythonic
*

Neutral because:

Bad because:
* Harder to enforce consistency in how the nodes are created

## More Information

This decision was inspired in part by the `py_trees` [documentation](https://py-trees.readthedocs.io/en/devel/the_crazy_hospital.html)
(in the context of composite nodes):

> Don’t subclass merely to auto-populate it, build a create_<xyz>_subtree() library instead

Which got us thinking about using factory methods to help maintain a clean separation between the `vultron.bt.base`
module and the things that live above it.
