---
title: Behavior Tree Reusability and Composability Patterns
status: active
description: >
  Design patterns for composable, reusable BT nodes and subtrees; vocabulary
  for reusability and concrete anti-patterns.
related_specs:
  - specs/behavior-tree-integration.yaml
  - specs/behavior-tree-node-design.yaml
  - specs/bt-composability.yaml
related_notes:
  - notes/bt-composability.md
  - notes/bt-integration.md
  - notes/use-case-behavior-trees.md
relevant_packages:
  - py_trees
  - vultron/bt
  - vultron/core/behaviors
---

# Behavior Tree Reusability and Composability Patterns

## Overview

This note captures the design patterns for composable, reusable behavior tree
nodes and subtrees in Vultron. The goal is to establish a clear vocabulary for
what makes BT code reusable vs. one-off, and to provide concrete anti-patterns
to avoid.

**See also:**

- `notes/bt-integration.md` — Architecture decisions and design rationale
- `notes/vultron-bt.txt` — Canonical simulation BT structure (reference)
- `specs/behavior-tree-integration.yaml` — Formal requirements (BT-06-*)
- `specs/behavior-tree-node-design.yaml` — Node design specification (BTND-01 through BTND-04)

---

## Foundational Concepts

### Trunk-Removed Branches Model

Vultron's prototype uses an **event-driven** architecture: one incoming
ActivityStreams activity triggers one use-case handler, which runs a focused
behavior tree and completes.

The **canonical simulation BT** (`vultron/bt/`) is a single large
`CvdProtocolRoot` tree that ticks continuously, branching on every cycle.
The prototype cannot replicate this — it receives discrete messages and
must respond synchronously.

**Solution: Remove the trunk, keep the branches.**

Each use-case handler in `vultron/core/use_cases/` maps to a named subtree
in the canonical BT. When an activity arrives:

1. The dispatcher identifies the semantic type (CreateReport, ProposeEmbargo, etc.)
2. The corresponding use-case handler is invoked
3. The handler orchestrates a py_trees BT that implements the canonical subtree
4. The BT executes to completion and returns

**Visual mapping:**

```text
Canonical tree:               Prototype:
CvdProtocolRoot               (trunk removed)
  ├─ ReceiveMessages    ──►   CreateReportReceivedUseCase
  │    └─ HandleRS      ──►   → ReceiveReportBT (subtree)
  │    └─ HandleEP      ──►   ProposeEmbargoReceivedUseCase
  │                           → ReceiveEmbargoBT (subtree)
  └─ PrioritizeBt       ──►   SvcEngageCaseUseCase
       └─ EngageFlow    ──►   → PrioritizeBT (subtree)
```

**Key implication**: The canonical tree structure IS the documentation. If the
tree shows that behavior B is a child of behavior A, then B MUST be
implemented as a BT subtree within A's tree — not as a procedural call after
A's BT completes.

---

## Fractal Composability Pattern

### Definition

**Fractal composability** means BT nodes and subtrees are self-contained,
parameterized components that can be nested at multiple levels of abstraction
without losing coherence or correctness.

A fractal BT is one where:

- Each subtree IS a complete, meaningful behavior (e.g., "engage the case",
  "validate the report", "emit an activity")
- The subtree can be triggered independently (via use-case entry point)
- The same subtree can also be composed as a child within a larger tree
- **Identity and role are constructor parameters**, not hard-coded constants

### Example: Parameterized Participant Creation

**Reusable subtree:**

```python
def create_case_participant_tree(
    case_id: str,
    actor_id: str,
    participant_role: str,  # ← role is parameterized
) -> py_trees.behaviour.Behaviour:
    """Create a CaseParticipant with the given role.
    
    Composable as a standalone use-case entry point, or as a child
    node within a larger workflow tree (e.g., CreateCaseBT).
    
    Args:
        case_id: VulnerabilityCase ID
        actor_id: Actor ID to add as participant
        participant_role: "vendor", "finder", "coordinator", etc.
    
    Returns:
        Root node of the participant-creation subtree
    """
    return py_trees.composites.Sequence(
        name=f"CreateParticipant_{participant_role}",
        memory=False,
        children=[
            ValidateParticipantRole(role=participant_role),
            CreateParticipantRecord(case_id=case_id, actor_id=actor_id, role=participant_role),
            EmitAddParticipantActivity(case_id=case_id, actor_id=actor_id),
            UpdateOutbox(),
        ],
    )
```

This tree is **reusable** because:

- Role is a parameter (not hard-coded "vendor")
- Actor and case IDs are parameters
- The tree can be invoked as a standalone trigger endpoint OR composed as
  a child of CreateCaseBT, ReceiveRecommendationBT, etc.

**Anti-pattern (non-reusable):**

```python
def create_finder_participant_node(case_id: str) -> py_trees.behaviour.Behaviour:
    """❌ WRONG — hard-coded to finder role only."""
    return py_trees.composites.Sequence(
        name="CreateFinderParticipant",  # ← role embedded in name
        children=[
            CreateParticipantRecord(
                case_id=case_id,
                actor_id="FINDER_ACTOR_ID",  # ← hard-coded constant
                role="finder",  # ← hard-coded string
            ),
            ...
        ],
    )
```

This is **not reusable** because the role and actor are built into the node.
If a use case needs to create a vendor, coordinator, or any other role,
this node cannot be reused — a new one must be written.

---

## Anti-Patterns to Avoid

### 1. Hard-Coded Actor Roles

**Pattern to avoid:**

```python
def emit_invite_node() -> py_trees.behaviour.Behaviour:
    """❌ Hardcoded to COORDINATOR role."""
    return CreateInviteActivity(
        actor_id="urn:example.org:actors:coordinator",  # ← hard-coded!
    )
```

**Correct pattern:**

```python
def emit_invite_node(actor_id: str) -> py_trees.behaviour.Behaviour:
    """✅ Actor role is a constructor parameter."""
    return CreateInviteActivity(actor_id=actor_id)
```

**Rationale**: Different actors (coordinator, vendor, finder) may need to
emit the same type of activity. If the role is hard-coded, you need a
separate node for each role. If role is a parameter, one node serves all.

### 2. Demo-Specific Logic in Reusable Nodes

**Pattern to avoid:**

```python
class CreateCaseParticipantNode(py_trees.behaviour.Behaviour):
    """❌ Mixes protocol logic with demo scaffolding."""
    
    def update(self) -> py_trees.common.Status:
        participant = create_participant(...)
        
        # Protocol work (good)
        case.add_participant(participant)
        
        # Demo scaffolding (BAD — should not be in this node)
        if os.environ.get("DEMO_MODE"):
            print(f"[DEMO] Created {participant}")  # ← demo-specific
            demo_logger.log(participant)            # ← demo-specific
        
        return py_trees.common.Status.SUCCESS
```

**Correct pattern:**

```python
class CreateCaseParticipantNode(py_trees.behaviour.Behaviour):
    """✅ Pure protocol logic, no demo scaffolding."""
    
    def update(self) -> py_trees.common.Status:
        participant = create_participant(...)
        case.add_participant(participant)
        
        # Logging goes to standard app logger, not demo-specific
        logger.info(f"Created participant {participant.id_}")
        
        return py_trees.common.Status.SUCCESS
```

**Rationale**: Demo scripts should call logging/printing code OUTSIDE the BT,
not embed demo logic into BT nodes. BT nodes are reused in multiple contexts
(API triggers, CLI commands, future MCP agents). Demo-specific code makes
the node un-reusable in non-demo contexts.

### 3. One-Off Subtrees Hard-Coded to Specific Workflows

**Pattern to avoid:**

```python
def create_finder_case_tree(
    case_obj: VulnerabilityCase,
    finder_actor_id: str,
) -> py_trees.behaviour.Behaviour:
    """❌ One-off tree coupling finder + case creation."""
    
    return py_trees.composites.Sequence(
        name="CreateFinderCaseFlow",
        children=[
            # ... finder-specific setup ...
            CreateCase(case_obj=case_obj),
            CreateFinderParticipant(finder_id=finder_actor_id),  # ← finder-specific
            SendFinderNotification(finder_id=finder_actor_id),   # ← finder-specific
            # ... more finder-specific logic ...
        ],
    )
```

This tree is **not reusable** because it's hard-wired to "finder + case creation".
If a coordinator or vendor needs to create a case, they cannot reuse this tree.

**Correct pattern (compositional):**

```python
def create_case_tree(case_obj: VulnerabilityCase, owner_actor_id: str) -> ...:
    """✅ Generic case creation, parameterized by owner."""
    return py_trees.composites.Sequence(
        name="CreateCaseFlow",
        children=[
            ValidateCase(case_obj=case_obj),
            PersistCase(case_obj=case_obj),
            CreateInitialParticipant(case_id=case_obj.id_, actor_id=owner_actor_id),
            CreateCaseActor(case_id=case_obj.id_),
            # ... generic workflow ...
        ],
    )

def receive_create_case_activity_tree(activity: CreateCaseActivity) -> ...:
    """✅ Specific entry point for incoming CreateCaseActivity."""
    case = coerce_to_case(activity.object_)
    owner_id = activity.actor  # ← owner determined from activity, not hard-coded
    
    return py_trees.composites.Sequence(
        name="ReceiveCreateCaseFlow",
        children=[
            create_case_tree(case, owner_id),  # ← compose generic tree
            # Possibly activity-specific post-processing (if any)
        ],
    )
```

**Rationale**: Separate generic reusable logic (case creation) from
activity-specific logic (extracting owner from the incoming activity).
Generic logic is composable; activity-specific logic is the integration point.

### 4. Duplicate Subtrees with Slight Variations

**Pattern to avoid:**

```python
# ❌ Two nearly identical subtrees
def create_vendor_participant_tree(...) -> ...:
    """Vendor-specific participant creation."""
    # 95% identical to create_finder_participant_tree()
    return py_trees.composites.Sequence(
        name="CreateVendorParticipant",
        children=[
            ValidateParticipant(role="vendor"),
            CreateParticipantRecord(...),
            EmitActivity(...),
        ],
    )

def create_finder_participant_tree(...) -> ...:
    """Finder-specific participant creation."""
    # 95% identical to create_vendor_participant_tree()
    return py_trees.composites.Sequence(
        name="CreateFinderParticipant",
        children=[
            ValidateParticipant(role="finder"),
            CreateParticipantRecord(...),
            EmitActivity(...),
        ],
    )
```

This violates DRY (Don't Repeat Yourself). If a bug is found in one, it must
be fixed in all copies.

**Correct pattern (parameterized):**

```python
def create_case_participant_tree(
    case_id: str,
    actor_id: str,
    role: str,  # ← single parameterized tree
) -> py_trees.behaviour.Behaviour:
    """✅ One tree, parameterized by role."""
    return py_trees.composites.Sequence(
        name=f"CreateParticipant_{role}",
        children=[
            ValidateParticipant(role=role),
            CreateParticipantRecord(case_id=case_id, actor_id=actor_id, role=role),
            EmitActivity(...),
        ],
    )
```

**Rationale**: Changes are made in one place, reducing maintenance burden and
risk of divergence.

---

## Node Design Guidelines

### Parameterization

All BT nodes MUST take required values as constructor parameters. Do NOT
look up values from global state, environment variables, or implicit context.

**Prefer:**

```python
class CreateActivityNode(py_trees.behaviour.Behaviour):
    def __init__(self, actor_id: str, target_id: str, **kwargs):
        super().__init__(**kwargs)
        self.actor_id = actor_id
        self.target_id = target_id
```

**Avoid:**

```python
class CreateActivityNode(py_trees.behaviour.Behaviour):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.actor_id = os.environ.get("ACTOR_ID")  # ← implicit dependency
        self.target_id = get_current_target_from_context()  # ← implicit
```

**Rationale**: Explicit parameters make dependencies visible, simplify
testing, and improve composability. Implicit lookups hide assumptions.

### Blackboard Key Naming

BT blackboard keys MUST use simplified names following `{noun}_{id_segment}`
pattern, where `id_segment` is the last path component of the object's URI.

**Examples:**

```python
# ✅ Correct
bb.set("case_abc123", case_obj)
bb.set("embargo_def456", embargo_obj)
bb.set("participant_vendor", participant_obj)

# ❌ Avoid (slashes cause py_trees hierarchical parsing issues)
bb.set("https://example.org/cases/abc123", case_obj)
bb.set("urn:vultron:embargo:def456", embargo_obj)
```

**Rationale**: py_trees treats slashes as path separators. Keys with slashes
are parsed hierarchically, breaking simple key lookups.

### Isolation from Demo Context

BT nodes MUST NOT depend on demo-specific modules, constants, or environment
variables. If a node needs to log, use Python's standard `logging` module,
not demo-specific loggers.

**Prefer:**

```python
import logging

logger = logging.getLogger(__name__)

class SomeNode(py_trees.behaviour.Behaviour):
    def update(self) -> Status:
        logger.info(f"Doing work: {self.name}")  # ← standard logger
        # ...
```

**Avoid:**

```python
from vultron.demo.utils import demo_logger  # ← demo-specific import

class SomeNode(py_trees.behaviour.Behaviour):
    def update(self) -> Status:
        demo_logger.demo_step(f"Doing work: {self.name}")  # ← demo-specific
        # ...
```

**Rationale**: Nodes imported by demo scripts should remain reusable outside
demo contexts (e.g., API handlers, CLI commands, future MCP agents).

### ActorConfig-Driven Roles

The local actor's default CVD roles MUST be sourced from `ActorConfig`
rather than hardcoded in BT nodes. This decouples the protocol logic from
demo assumptions (e.g., "the receiver is always a vendor").

**Pattern:**

```python
from vultron.core.models.actor_config import ActorConfig
from vultron.core.states.roles import CVDRoles

class CreateCaseOwnerParticipant(DataLayerAction):
    """Creates the case-owner participant for the local actor.
    
    Sources CVD roles from ActorConfig rather than hardcoding.
    Always includes CVDRoles.CASE_OWNER in the assigned roles.
    """
    
    def __init__(
        self,
        actor_config: ActorConfig,
        report_id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.actor_config = actor_config
        self.report_id = report_id
    
    def update(self) -> Status:
        roles = list(self.actor_config.default_case_roles)
        if CVDRoles.CASE_OWNER not in roles:
            roles.append(CVDRoles.CASE_OWNER)
        
        participant = VultronParticipant(
            attributed_to=self.actor_id,
            case_roles=roles,  # ← from config, not hardcoded
            ...
        )
        ...
```

**Why this matters:**

| Old approach | New approach |
|---|---|
| `case_roles=[CVDRoles.VENDOR]` hardcoded | `roles = actor_config.default_case_roles` |
| Breaks for coordinator-run nodes | Works for any CVD actor type |
| Must write a new node per role | One node, parameterized by config |

**ActorConfig placement:**

`ActorConfig` is a neutral Pydantic model in `vultron/core/models/` (or
`vultron/config.py`) — **not** inside `vultron/demo/`. This ensures BT
nodes can import it without violating the no-demo-layer-imports rule
(BTND-04-002, CFG-07-001).

**See also:**

- `specs/behavior-tree-node-design.yaml` BTND-05-001 through BTND-05-003
- `specs/configuration.yaml` CFG-07-001 through CFG-07-004

---

## Composability Patterns

### Subtree Composition

Reusable subtrees are composed by adding their root nodes as children of a
parent Sequence or Selector.

```python
def parent_tree(case_id: str, actor_ids: list[str]) -> py_trees.behaviour.Behaviour:
    """Parent tree that composes reusable participant-creation subtrees."""
    
    children = [
        ValidateCase(case_id=case_id),
        PersistCase(case_id=case_id),
    ]
    
    # Compose participant-creation subtrees
    for actor_id in actor_ids:
        children.append(
            create_case_participant_tree(
                case_id=case_id,
                actor_id=actor_id,
                role="participant",
            )
        )
    
    return py_trees.composites.Sequence(
        name="ParentTree",
        children=children,
    )
```

### Selector for Alternatives

Use Selectors (OR logic) when multiple branches represent alternative paths:

```python
def handle_case_state_tree(case_id: str) -> py_trees.behaviour.Behaviour:
    """Selector: either engage or defer the case."""
    
    return py_trees.composites.Selector(
        name="HandleCaseState",
        memory=False,
        children=[
            engage_case_if_priority_high_subtree(case_id),
            defer_case_subtree(case_id),  # ← fallback if engage fails
        ],
    )
```

### Sequence for Ordered Steps

Use Sequences (AND logic) when steps must execute in order:

```python
def process_activity_tree(activity: Activity) -> py_trees.behaviour.Behaviour:
    """Sequence: validate → extract → persist → emit."""
    
    return py_trees.composites.Sequence(
        name="ProcessActivity",
        memory=False,
        children=[
            ValidateActivity(activity=activity),
            ExtractSemanticContent(activity=activity),
            PersistToDataLayer(),
            EmitOutboundActivity(),
        ],
    )
```

---

## Testing Composability

When writing tests for reusable BT nodes and subtrees:

1. **Test in isolation**: Create minimal test fixtures that invoke the node
   without external context
2. **Test parameterization**: Verify that changing parameters produces
   expected behavior variations
3. **Test composition**: Verify that nodes work correctly when composed into
   parent trees
4. **Avoid fixture coupling**: Do not embed demo-specific test data or
   setup in test fixtures

**Example:**

```python
def test_create_participant_tree_with_vendor_role():
    """✅ Test parameterized node with different role."""
    tree = create_case_participant_tree(
        case_id="case_123",
        actor_id="actor_vendor",
        role="vendor",  # ← parameterized role
    )
    
    # Verify tree structure
    assert tree.name == "CreateParticipant_vendor"
    
    # Verify execution
    status = tree.tick_once()
    assert status == py_trees.common.Status.SUCCESS

def test_create_participant_tree_with_finder_role():
    """✅ Same test, different role — proves parameterization works."""
    tree = create_case_participant_tree(
        case_id="case_123",
        actor_id="actor_finder",
        role="finder",  # ← different parameter
    )
    
    assert tree.name == "CreateParticipant_finder"
    status = tree.tick_once()
    assert status == py_trees.common.Status.SUCCESS
```

---

## Anti-Pattern Reference (Quick Checklist)

Before adding a new BT node or subtree, check:

- [ ] **No hard-coded actor roles** — Actor identities are constructor parameters
- [ ] **No demo-specific imports** — No direct imports from `vultron.demo`
- [ ] **No environment-variable dependencies** — Use constructor parameters
- [ ] **No singleton patterns** — All state is parameter-passed or in DataLayer
- [ ] **No duplicate logic** — Similar operations are extracted into parameterized
      helpers
- [ ] **Blackboard keys avoid slashes** — Use `{noun}_{id_segment}` pattern
- [ ] **Composable in parent trees** — The subtree can be added as a child
      to other trees
- [ ] **Testable in isolation** — No external setup required to test the node

---

## Related Reading

- `notes/bt-composability.md` — Fractal pattern in depth, "trunkless branch"
  clarification, simulator navigation guide, and BT idiom examples
- `notes/bt-integration.md` — Architecture decisions and design rationale
- `notes/vultron-bt.txt` — Canonical simulation BT structure (reference)
- `notes/use-case-behavior-trees.md` — Use-case orchestration patterns
- `specs/bt-composability.yaml` — Formal composability requirements (BTC-01 through BTC-04)
- `specs/behavior-tree-integration.yaml` — Formal requirements (BT-06-*)
- `specs/behavior-tree-node-design.yaml` — Node design specification (BTND-01 through BTND-05)
