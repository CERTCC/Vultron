# Compose Before Create

Before writing any new class or function, confirm that the functionality
does not already exist in the codebase. Implementing a duplicate is always
worse than composing from or subclassing what already exists.

## Principle

Search the target subsystem for classes or functions whose names,
docstrings, or semantics overlap with the code you are about to write. If a
match exists, compose or subclass — do not re-implement. If the task spans
multiple subsystems, search each one.

## Per-Subsystem Search Patterns

### Use cases (`vultron/core/use_cases/`)

```bash
grep -rn "<semantic keyword>" vultron/core/use_cases/
graphify query "<use case action or message type>"
```

A match in `handlers/` or `triggers/` means the protocol action is already
wired. Reuse the existing use case rather than writing a parallel handler.

### Wire handlers (`vultron/wire/as2/`)

```bash
grep -rn "<message type or pattern name>" vultron/wire/as2/
graphify query "<wire activity type>"
```

A match in `extractor.py` or `patterns/` means the wire pattern is already
registered. Extend an existing entry when semantics overlap; do not create a
competing pattern for the same activity structure.

### Adapters (`vultron/adapters/`)

```bash
grep -rn "<port name or adapter action>" vultron/adapters/
graphify query "<adapter keyword>"
```

Confirm the port contract before implementing. A port method already defined
in `vultron/core/ports/` with a stub in `vultron/adapters/driven/` should be
extended, not shadowed.

### Demo helpers (`vultron/demo/helpers/`)

```bash
grep -rn "<helper name or scenario action>" vultron/demo/helpers/
graphify query "<demo action>"
```

Demo helpers are strictly DRY — reuse `receiver_engages_case()`,
`run_direct_path_rm_triage()`, and similar shared helpers rather than
inlining their bodies in a new scenario. See `vultron/demo/AGENTS.md`
§ "Extract Before Reuse" and DEMOMA-17-001.

## BT Domain (`vultron/core/behaviors/`)

For behavior tree nodes, run these searches first, then consult
`vultron/core/behaviors/AGENTS.md` § "Compose Before Create: Node Discovery
Gate" for the domain base-class table and AC-1 compliance requirements.

**Node inventory** — search for existing nodes whose protocol state, domain,
or semantic action overlaps with what you are about to implement:

```bash
grep -r "<target state value or action name>" vultron/core/behaviors/<domain>/nodes/
graphify query "<action name or protocol state>"
```

If a match exists, compose or subclass — do not re-implement. After
completing this inventory, apply the base-class and AC-1 checks from
`vultron/core/behaviors/AGENTS.md`.
