# Behavior Tree Node Design Specification

## Overview

Formal requirements for BT node parameterization, composability, and reuse
in `vultron/core/behaviors/`. These requirements operationalize the fractal
composability pattern described in `notes/bt-reusability.md`.

**Source**: IDEA-26041703; `notes/bt-reusability.md`; Priority 360.

**Note**: This spec addresses *how* BT nodes are designed and structured. The
*when-to-use BTs* and *execution model* requirements live in
`specs/behavior-tree-integration.md`.

---

## Node Parameterization

- `BTND-01-001` BT nodes MUST NOT hard-code actor identities, CVD roles, case
  IDs, or any context that varies by usage site; these values MUST be
  constructor parameters.
  - **Rationale**: Hard-coded context values prevent reuse across actors or
    scenarios and couple the node to a single workflow.
  - **Scope limit**: Only *usage-varying* context must be parameterized. Fixed
    semantic transitions (e.g., a node whose sole purpose is `RM.RECEIVED →
    RM.VALID`) MUST NOT be forced to accept a state enum parameter just to
    satisfy this rule.
  - `BTND-01-001 refines BT-06-004`

- `BTND-01-002` BT nodes MUST NOT read actor identity, case ID, or CVD role
  from environment variables, module-level globals, or any implicit ambient
  context. All variable inputs MUST arrive via constructor parameters or the
  documented blackboard interface.

- `BTND-01-003` When a BT node name is derived from a parameterized value
  (e.g., role or actor ID), the name MUST be constructed from that parameter
  at instantiation time, not hard-coded as a string literal.
  - `BTND-01-003 refines BT-06-004`

---

## Composability and Reuse

- `BTND-02-001` Logic that appears in two or more BT nodes or subtrees MUST
  be extracted into a shared, parameterized node or factory function in a
  neutral shared module (see `BTND-04-001`).
  - **Semantic-preserving constraint**: Consolidation is only valid when the
    merged implementation preserves all protocol-visible behavior — state
    transitions, emitted activities, ordering, idempotency, and addressee
    derivation — from all merged variants.
  - `BTND-02-001 refines BT-06-004`

- `BTND-02-002` Each BT subtree SHOULD be independently triggerable as a
  use-case entry point AND composable as a child of a larger subtree.
  - **Rationale**: This is the "fractal composability" pattern. Subtrees that
    can only be used one way are candidates for refactoring.
  - `BTND-02-002 refines BT-06-002`

- `BTND-02-003` New BT subtrees SHOULD be verified against
  `notes/vultron-bt.txt` (the canonical simulation BT structure) to confirm
  structural correspondence before committing.
  - `BTND-02-003 refines BT-06-002`

- `BTND-02-004` A shared BT node or subtree that models a generic operation
  (e.g., "create a case participant with any role") SHOULD replace all
  role-specific one-off variants (e.g., `CreateFinderParticipantNode`,
  `CreateVendorParticipantNode`) once the shared version is available.
  - **Rationale**: Reduces maintenance surface; fixes and improvements apply
    consistently across all use sites.

---

## Blackboard Interface Contracts

- `BTND-03-001` Each BT node that reads from or writes to the py_trees
  blackboard MUST declare all blackboard keys it uses in its `setup()` method
  via `register_key()`.
  - **Rationale**: Undeclared blackboard reads create hidden dependencies that
    break composability and make tests fragile.
  - `BTND-03-001 refines BT-03-003`

- `BTND-03-002` A BT node MUST NOT read a blackboard key that was not
  registered with at least `READ` access in `setup()`.
  - `BTND-03-002 refines BT-03-003`

- `BTND-03-003` A BT node's docstring SHOULD document all blackboard keys it
  reads and writes, including the expected type and the node that produces the
  value for each READ key.

---

## Module Ownership

- `BTND-04-001` BT nodes or subtrees that are used by more than one domain
  module (e.g., by both `case/` and `report/`) MUST be defined in the shared
  `vultron/core/behaviors/helpers.py` module or a purpose-built shared module
  within `vultron/core/behaviors/`. Domain-specific modules MUST NOT import
  BT nodes from sibling domain modules.
  - **Rationale**: Cross-domain node imports create tight coupling and
    circular-import risk. Neutral shared ownership makes the dependency
    structure explicit.
  - `BTND-04-001 refines ARCH-04-001`

- `BTND-04-002` BT nodes MUST NOT import from `vultron/demo/` or any other
  demo-layer module. Demo-specific context (step descriptions, demo loggers,
  demo flags) belongs in demo scripts, not in BT nodes.

---

## Actor Configuration for Participant Nodes

- `BTND-05-001` The `CVDRoles` enum MUST include a `CASE_OWNER` flag value
  representing the actor who owns and manages a `VulnerabilityCase`.
  - **Rationale**: Case ownership is a protocol-significant relationship
    distinct from the CVD roles (VENDOR, COORDINATOR, etc.). When a vendor
    or coordinator receives a report and creates a case, they are both the
    receiving CVD actor (VENDOR or COORDINATOR) and the case owner.
    Representing this explicitly avoids hardcoding the assumption that the
    case creator is always a vendor.
  - **Refactor note**: The `CVDRoles` Flag enum SHOULD eventually be
    refactored to a `list[CVDRoles]` using a StrEnum, so that participant
    role assignments read as plain strings in persisted records (e.g.,
    `["vendor", "case_owner"]` instead of a bitmask). Capture as a follow-on
    task when adding `CASE_OWNER`.

- `BTND-05-002` `CreateInitialVendorParticipant` MUST be replaced by a
  `CreateCaseOwnerParticipant` node that:
  - Sources the local actor's CVD roles from
    `ActorConfig.default_case_roles` (see `CFG-07-002`), rather than
    hardcoding `CVDRoles.VENDOR`.
  - Always includes `CVDRoles.CASE_OWNER` in the participant's roles
    (appending it if not already present in the configured list).
  - Retains all RM-state seeding logic from `CreateInitialVendorParticipant`
    (deterministic status record reuse from report-phase, initial RM state
    parameterization).
  - **Rationale**: "Vendor" is a demo-specific assumption. In the general
    protocol a coordinator, deployer, or other role may equally receive a
    report and become the case owner. The node MUST NOT know or care which
    CVD role the actor plays — only that they are the case owner.
  - `BTND-05-002 refines BTND-01-001`

- `BTND-05-003` The `CreateFinderParticipantNode` backward-compatibility alias
  (currently `CreateFinderParticipantNode = CreateCaseParticipantNode`) MUST
  be removed. All call sites MUST use `CreateCaseParticipantNode` directly
  with an explicit `roles` parameter.
  - **Rationale**: Alias names carry the old "finder-specific" framing and
    mislead readers about the node's actual generality.

---

## Verification

### BTND-01-001, BTND-01-002, BTND-01-003

- Code review: BT node constructors in `vultron/core/behaviors/` accept actor
  ID, case ID, and role as explicit constructor parameters where used.
- Code review: No node reads from `os.environ`, module-level globals, or demo
  constants inside `update()` or `initialise()`.
- Code review: Node names derived from parameterized values are built from
  those values (e.g., `f"CreateParticipant_{role}"`), not hard-coded strings.

### BTND-02-001, BTND-02-004

- Code review: No two nodes in `vultron/core/behaviors/` contain
  functionally identical `update()` bodies; any near-duplicate is extracted
  to a shared parameterized node.
- Unit test: A shared parameterized node produces the same protocol-visible
  outcome as each of its consolidated predecessors for the same inputs.

### BTND-03-001, BTND-03-002

- Code review: Every call to `self.blackboard.get(key)` or
  `self.blackboard.<key>` in a node is preceded by a `register_key()` call
  for that key in `setup()`.
- Unit test: A fresh node instance passes py_trees blackboard validation
  without `KeyError` or unregistered-key warnings.

### BTND-04-001

- Code review: No node in `vultron/core/behaviors/case/` or
  `vultron/core/behaviors/report/` imports a node class directly from the
  other sibling domain module; shared nodes are imported from
  `vultron.core.behaviors.helpers` or another neutral module.

### BTND-05-001

- Code review: `CVDRoles` in `vultron/core/states/roles.py` contains a
  `CASE_OWNER` member.
- Unit test: `CVDRoles.CASE_OWNER` is usable as a flag value (can be
  combined with VENDOR, COORDINATOR, etc.).

### BTND-05-002

- Code review: `CreateCaseOwnerParticipant` exists in
  `vultron/core/behaviors/case/nodes.py`; `CreateInitialVendorParticipant`
  is removed.
- Code review: `CreateCaseOwnerParticipant.__init__` reads roles from an
  `ActorConfig` object (or equivalent) rather than hardcoding `CVDRoles.VENDOR`.
- Code review: `CVDRoles.CASE_OWNER` is always present in the participant
  record created by `CreateCaseOwnerParticipant`.
- Unit test: Instantiating `CreateCaseOwnerParticipant` with an
  `ActorConfig` whose `default_case_roles` is `[CVDRoles.COORDINATOR]`
  yields a participant with roles `COORDINATOR | CASE_OWNER`.

### BTND-05-003

- Code review: No file in `vultron/` contains
  `CreateFinderParticipantNode`.
- Unit test: `from vultron.core.behaviors.case.nodes import
  CreateFinderParticipantNode` raises `ImportError`.

## Related

- **Design notes**: `notes/bt-reusability.md` — fractal composability pattern,
  trunkless branch model, and anti-pattern reference
- **BT execution model**: `specs/behavior-tree-integration.md` — BT-06-001
  through BT-06-006, DataLayer integration, actor isolation
- **Object IDs / blackboard keys**: `specs/object-ids.md` OID-01-*
- **Architecture layering**: `specs/architecture.md` ARCH-04-001
- **Actor configuration**: `specs/configuration.md` CFG-07-001 through
  CFG-07-004
