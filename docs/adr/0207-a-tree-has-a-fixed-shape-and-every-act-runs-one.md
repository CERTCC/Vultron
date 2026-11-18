---
status: accepted-provisional
date: 2026-11-16
created: 2026-11-16
updated: 2026-11-16
revision: 2
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0087, ADR-0089, ADR-0135; specs/behavior-tree-integration.yaml
  BT-05, BT-17; notes/bt-integration.md; issues #5584, #5572, #6514
informed: []
stakeholder_type: [project-contributor]
---

# A Tree Has a Fixed Shape, and Every Act Runs One

## Context and Problem Statement

A node can start a tree run of its own.
About twenty-five sites do: a node holds a writer subtree and runs it through `BTBridge.execute_with_setup` from `update()`, and every ledger commit runs `create_commit_log_entry_tree` the same way, once per entry.
Those subtrees are built from the data they act on (`create_commit_log_entry_tree(case_id, object_id, semantic_type)`), so a step that commits one entry per participant builds one tree per participant while the outer tree runs.

ADR-0135 made a received delivery one tree as seen from the use case, and ADR-0089 made the participant-status writer a real tree child.
Neither reached inside a node, and the nested bridge run took the place of the nested `update()` call ADR-0089 removed.

A nested run can hide the inner tree's internal error behind the outer node's verdict unless each site carries it across by hand, and it hides the subtree from anything that walks the tree.
That second point is why nothing releases a py_trees blackboard client (#5584).
Every node that attaches a blackboard client registers it in the process-global registry when the node is built, and the only place to release a tree's clients is the end of its run.
A walk at the end of the run misses every subtree a node holds outside its children.
Releasing at the end of a nested run unregisters a subtree the parent may tick again.

How should a tree be shaped, so that every act runs one tree and a run can release everything it registered?

## Decision Drivers

- Every act runs one tree that a reader, the ratchets and a teardown walk can all see whole (ADR-0135).
- An internal error anywhere in the act surfaces as the act's internal error (ADR-0095).
- Nothing a tree run registers outlives the run, in a server or in a test.
- No state carries from one act to the next through node objects.

## Considered Options

How a step that repeats a run-time number of times is shaped:

- **A loop over a blackboard work list, running one fixed subtree.**
- **A for-each composite that builds one subtree per item as children at tick time.**
- **A plain function in place of the subtree**, with the commit's guard, transaction and fan-out moved inside it.

How long a tree lives:

- **Built fresh for each act, its clients released when the run ends.**
- **Built once per tree type and reused for every act.**

How far "data on the blackboard" reaches (revision 2):

- **Every tree: no node constructor and no tree factory takes a per-act value.**
- **Only the trees that learn a value while running**, with build-time values left as constructor arguments.

## Decision Outcome

Chosen: **a loop over a blackboard work list running one fixed subtree**, **a tree built fresh for each act**, and (revision 2) **every tree, with no per-act value in a node constructor or tree factory**.

### A tree's shape is fixed by the act

A tree factory builds the shape the act needs.
Which case, which object and how many entries are data, and data reaches the nodes through the blackboard, not through node constructors.
A node never builds or runs a tree while a tree runs, so each act is one tree run.

### A repeated step is a loop over a work list

A step that repeats a number of times known only at run time is one subtree under a loop.
A node upstream writes the work list to the blackboard.
The loop puts the current item on the blackboard and ticks the same subtree once for each item.
The subtree reads its inputs from the blackboard, so it has the same shape for one item or fifty.

The ledger commit becomes such a subtree.
A node that commits one entry composes it as a child; a node that commits several writes the work list and composes the loop.

### Each act builds its tree, and the run releases what it registered

A tree is built for one act and dropped after it.
When the run ends, on every outcome, the runner releases every blackboard client the tree's nodes and the runner itself registered, without clearing stored keys.
Restoring stored keys stays the bridge's job (BT-17-007).

### Every per-act value reaches a node through a named key, in every tree

Revision 2 (#6514) widens "data reaches the nodes through the blackboard" from loop subtrees to every tree.
No node constructor and no tree factory takes a per-act value: a case, report, embargo or actor id, or an object the message carries.
A constructor takes configuration only, such as a name, a port name, a role, a declared state or a child.
Each per-act value has one name in one key vocabulary.

A tree factory declares the keys its tree needs.
That declaration is the tree's behavior contract: given these values, this logic completes the act.
A published behavior spec renders it with the tree's shape.

Each declared key has one source in the tree.
The runner seeds a key before the first tick when the act's event or trigger request carries the value, which reads no store.
A value that only the store holds, such as a report's case or a fault's refused entry, is published by a lookup node at the front of the tree.
In a received tree the lookup's miss is a declared refusal, because the use case and the runner read no store (ADR-0195).
The runner raises a wiring error rather than tick a tree whose declared key has no source.

A narrower option kept the rule to the trees that learn a value only while running and left build-time values as constructor arguments.
It was rejected: two styles of input supply would coexist, and a tree built with its data wired in could not become a subtree or a loop body without the same migration later.

### Consequences

- Good: a walk over the tree reaches every node, so release, diagnostics and ratchets see the whole act.
- Good: an internal error in a commit is the act's internal error, with no hop to carry it across.
- Good: the client registry returns to its size before the act, so a long-running container does not grow and a test sees no client from an earlier one.
- Bad: nodes that branch on a nested run's result move that branching into composites, and the commit's inputs move from constructor arguments to blackboard keys, which touches many files.
- Bad: every factory and node that bakes in a per-act value moves to a declared key, which touches most tree modules; a shrink-only ratchet counts what is left.
- Bad: a loop's per-item inputs are blackboard keys, so each needs its handoff-key name (BTND-03-004) and its restore on every outcome.

## Validation

An architecture test lists the sites that still start a nested tree run and fails when a new one appears; the list only shrinks, and ends empty.
A test delivers an activity and asserts the client registry is the size it was before the delivery.
An architecture ratchet lists every node constructor and tree factory that still takes a per-act value; the list only shrinks, and ends empty.
An architecture test builds every tree and fails when a node reads a key its tree neither declares nor publishes.

## Pros and Cons of the Options

### A for-each composite that builds children at tick time

- Good: keeps the commit a visible tree, and every client is inside the tree.
- Bad: the tree's shape follows the data, so the same act has a different tree each time, and every factory that bakes data into constructors stays as it is.

### A plain function in place of the subtree

- Good: the smallest change.
- Bad: the commit's steps stop reporting node failure reasons, and the commit is no longer a tree a reader can see.

### Built once per tree type and reused

- Good: the client registry stops growing with no release at all.
- Bad: every node's instance attributes outlive the act, which moves hidden process-wide state into the nodes.
  Each node would need proof that `initialise()` resets everything it reads.

### Only the trees that learn a value while running

- Good: leaves every tree that knows its values at build time as it is, so far fewer files change.
- Bad: two styles of input supply coexist, and a tree built with its data wired in cannot become a subtree or a loop body without the same migration later.

## More Information

This extends ADR-0135's one tree per delivery from the use case down into the nodes, and finishes ADR-0089's rule that the participant-status writer is a real tree child.
It supersedes neither.
The current rules live in `specs/behavior-tree-integration.yaml` BT-25, in `specs/behavior-tree-node-design.yaml` BTND-01-008, BTND-01-009 and BTND-03-022, and in `notes/bt-integration.md` § "One Fixed-Shape Tree per Act".
