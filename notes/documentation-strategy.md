# Documentation Strategy Notes

## Documentation Chronology and Trust Levels

The Vultron documentation has multiple generations, written at different
times with different purposes. Understanding this chronology is critical for
correctly interpreting documentation when it conflicts with implementation.

### Generation 1: Pre-implementation design docs

**Files**: `docs/topics/**/*.md`, `docs/reference/formal_protocol/**/*.md`,
`docs/howto/**/*.md`

These were written **before the ActivityStreams-based implementation** and
served as the original source material for early implementation iterations.
They describe the intended behavior patterns, state machine logic, and formal
protocol definitions.

**Trust**: High for understanding *intent and design rationale*. Low for
*specific field names, class hierarchies, or API details*, as these changed
with the ActivityStreams adoption.

### Generation 2: State-based model and simulation

**Files**: `vultron/case_states/**/*.py`, `vultron/bt/**/*.py`,
`vultron/demo/vultrabot.py`

These were some of the earliest Python implementations, based on:

- [*A State-Based Model for Coordinated Vulnerability Disclosure*](
  https://www.sei.cmu.edu/documents/1952/2021_003_001_737890.pdf)
  (CMU/SEI-2021-SR-021) — basis for `vultron/case_states/hypercube.py` and
  the VFD/PXA state machines.
- [*Designing Vultron*](
  https://www.sei.cmu.edu/documents/1954/2022_003_001_887202.pdf)
  (CMU/SEI-2022-SR-019) — basis for the behavior tree simulator in
  `vultron/bt/**/*.py` and `vultron/demo/vultrabot.py`.

These implementations came **before** the decision to use ActivityStreams
vocabulary. They remain valuable as reference implementations for protocol
logic, but MUST NOT be directly reused in prototype handlers. See
`notes/bt-integration.md` for the BT translation strategy.

### Generation 3: Current ActivityStreams-based implementation

**Files**: `vultron/as_vocab/**/*.py`, `vultron/api/**/*.py`,
`vultron/behaviors/**/*.py`, `vultron/activity_patterns.py`,
`vultron/semantic_map.py`, etc.

This is the current prototype codebase. Documentation in `docs/howto/activitypub/`
and `specs/**/*.md` reflects this generation.

---

## When Documentation Diverges from Implementation

When the implementation significantly diverges from the documentation,
evaluate:

1. **Is the divergence intentional?** If the ActivityStreams adoption required
   a design change, the documentation may be deliberately different and should
   be updated to reflect the new design.

2. **Is the implementation wrong?** If the implementation drifts from the
   intended design without a documented reason, consider whether the
   implementation should be corrected.

3. **Is the documentation outdated?** If the documentation reflects an earlier
   design that has since been superseded, mark it as historical or update it.

**Decision framework**:
- Divergence with documented rationale → update docs to reflect new reality.
- Divergence without clear rationale → investigate before changing either.
- Outdated design docs with no corresponding implementation → mark as
  historical or archive.

---

## Process Models and Formal Protocol Documentation

### Process Models

`docs/topics/background/overview.md` provides a high-level overview. Detailed
process model documentation is in `docs/topics/process_models/`:

- `rm/` — Report Management state machine
- `em/` — Embargo Management state machine
- `cs/` — Case State transitions and interaction with RM/EM
- `model_interactions/` — how the three state machines interact

These describe the **intended behavior** of protocol participants and were
used as the design source for the behavior tree simulator in `vultron/bt/`.

### Formal Protocol

`docs/reference/formal_protocol/` provides formal state machine definitions:

- `states.md` — formal state enumeration
- `transitions.md` — allowed state transitions with conditions
- `messages.md` — message types and their semantic effects

These are normative for protocol correctness. When implementing new handlers
or BT nodes, verify that state transitions conform to the formal protocol
definitions.

---

## Behavior Simulator as Implementation Reference

`vultron/bt/**/*.py` contains a substantial behavior tree simulator that
encodes the protocol logic from *Designing Vultron*. Although it uses a
custom BT engine incompatible with the prototype's `py_trees`-based approach,
it is an invaluable reference for:

1. **State machine logic**: Condition checks, transition guards, and ordering
   constraints are encoded as BT node compositions.
2. **Protocol behavior patterns**: The full CVD workflow (report intake,
   validation, embargo management, case coordination) is represented as
   composable BT subtrees.
3. **Correspondence with documentation**: The simulator trees correspond
   directly to the documentation in `docs/topics/behavior_logic/*.md`.

### Documentation-to-Simulator Correspondence

| Documentation file | Simulator module |
|-------------------|-----------------|
| `behavior_logic/cvd_bt.md` | `vultron/bt/` (top-level) |
| `behavior_logic/em_bt.md` | `vultron/bt/embargo_management/` |
| `behavior_logic/do_work_bt.md` | `vultron/bt/` (do_work nodes) |
| `behavior_logic/fix_dev_bt.md` | `vultron/bt/` (fix dev subtrees) |
| `behavior_logic/deployment_bt.md` | `vultron/bt/` (deployment subtrees) |
| `behavior_logic/monitor_threats_bt.md` | `vultron/bt/` (monitoring subtrees) |
| `behavior_logic/id_assignment_bt.md` | `vultron/bt/` (ID assignment subtrees) |
| `behavior_logic/acquire_exploit_bt.md` | `vultron/bt/` (exploit acquisition) |

**Recommended approach** for mining the simulator: Map each `vultron/bt/`
subtree to its documentation source, then identify which prototype handlers
the subtree informs. Use this as a guide for implementing BT nodes in
`vultron/behaviors/`. See `notes/bt-integration.md` for the translation
strategy.

---

## "Do Work" Behaviors: Human and Agent Tasks

The behavior tree documentation defines a `do work` parallel node as a
container for tasks that are largely **outside the protocol's automated scope**.
These represent work participants must perform that results in protocol-visible
state transitions.

**`do work` sub-behaviors** (from `docs/topics/behavior_logic/do_work_bt.md`):

- **Deployment** — deploying a fix (triggers `D` event in CS)
- **Develop fix** — developing a patch (triggers `F` event in CS)
- **Report to others** — coordinating with other participants
- **Publication** — publishing vulnerability information (triggers `P` event)
- **Monitor threats** — watching for exploits/attacks (triggers `X`, `A` events)
- **Assign CVE ID** — identifier assignment (external coordination)
- **Acquire exploit** — obtaining exploit samples for analysis
- **Other work** — participant-specific tasks (explicitly a placeholder)

**Automation potential** (not yet analyzed systematically):

- **High automation potential**: CVE ID assignment requests (structured API
  calls to CVE Numbering Authorities), monitoring for exploit publication
  (external feed integration), monitoring for active attacks (threat intel
  feeds).
- **Medium automation potential**: Structured reporting to other participants
  (message composition and sending is automatable; decision to report is not).
- **Low automation potential**: Fix development, fix deployment, embargo
  negotiation — these require domain expertise and human judgment.

**Implication for the prototype**: The `do work` items are natural candidates
for posing as tasks to a human or AI agent. Future UI design or agent
integration should expose these as actionable work items given the current
case state (see `notes/case-state-model.md` for the potential actions
framework).

---

## ISO Standards Cross-References

High-level cross-references to relevant ISO standards are documented in
`docs/reference/iso_crosswalks/`:

- `iso_29147_2018.md` — ISO/IEC 29147:2018 (Vulnerability Disclosure)
- `iso_30111_2019.md` — ISO/IEC 30111:2019 (Vulnerability Handling Processes)
- `iso_5895_2022.md` — ISO/IEC 5895:2022 (Multi-Party Coordinated Vulnerability Disclosure)

**Current state**: Cross-references are at a high level, mapping general
protocol concepts to ISO standard sections.

**Future work**: As the ActivityStreams vocabulary implementation matures,
it would be valuable to add more specific cross-references — linking
particular `MessageSemantics` values, handler behaviors, and vocabulary
types to the ISO standard requirements they satisfy. This would help
demonstrate standards alignment and identify any gaps.

**Priority**: Low for the prototype, but useful for eventual standardization
efforts or external communication about the project's standards alignment.

---

## Archiving Historical Documentation

As the prototype matures, some documentation may be appropriate to archive
into a clearly marked "historical" section rather than delete:

- `docs/howto/case_object.md` — original UML design superseded by
  ActivityStreams model; worth preserving as historical reference.
- Some `docs/topics/process_models/` content — predates ActivityStreams;
  may be worth preserving with a note about its historical context.
- `docs/reference/formal_protocol/` — still normative; do NOT archive.

A reasonable convention: add a front-matter note to historical docs stating
the document predates the ActivityStreams implementation and may not reflect
current design. This preserves historical context without causing confusion.
