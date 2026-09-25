---
description: >
  The behavior trees in `vultron/core/behaviors/`, rendered from their factory
  functions.
stakeholder_type: [project-contributor]
---

# Behaviors Reference

This section provides auto-generated reference documentation for the behavior trees
implemented in `vultron/core/behaviors/`.

The trees are rendered using `py_trees.display.unicode_tree()` and instantiated
directly from their factory functions to reflect the current implementation.

!!! tip "Relationship to Behavior Logic docs"

    The [Behavior Logic](../../topics/behavior_logic/index.md) section in the topics chapter
    contains narrative explanations and Mermaid diagrams that reflect the *simulator-era*
    design from `vultron/bt/`.
    The pages in **this** section show the *current* implementation from `vultron/core/behaviors/`.

## Categories

| Page | Description |
|---|---|
| [Report Management Handlers](rm_handlers.md) | Receive-side and trigger-side RM trees |
| [Embargo Management Handlers](em_handlers.md) | Embargo lifecycle management trees |
| [Case Handlers](case_handlers.md) | Case receive-side trees |
| [Case State Handlers](cs_handlers.md) | Case State (CS) receive-side trees |
