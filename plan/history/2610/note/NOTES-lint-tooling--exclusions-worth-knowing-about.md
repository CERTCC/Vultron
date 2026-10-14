---
source: NOTES-lint-tooling--exclusions-worth-knowing-about
timestamp: '2026-10-14T14:26:28.911770+00:00'
title: 'lint-tooling: PLC0415 and G004 exclusion history'
type: note
---

Archived from `notes/lint-tooling.md` by #4498: the section recounted how the
two provisional `ignore` entries (`PLC0415`, `G004`) were removed
(#3949, #3950, #3991) and tabulated how each import cycle was broken. That work is
delivered. The lasting rules (both rules stay enabled, test-local imports are
exempt, a new cycle is broken by moving the symbol out of the package
`__init__` edge, no PEP 562 `importlib` deferral, no `ignore` entry cites a
tracking issue) stay in `notes/lint-tooling.md` § "Rules that stay enabled".

---

## Exclusions worth knowing about

**`PLC0415` (`import-outside-top-level`) was excluded in the configuration that
issue #3352 landed, and #3949 deleted that entry and placed the markers; #3950
drained them, so `vultron/` carries none.** Its ADR-0094 row was provisional and
pointed at #3350, which asked whether CS-05-002's "last resort" described the
design or an aspiration. The planning measurement answered it: hoisting every
function-local import in `vultron/` to module level and importing every module
showed that the overwhelming majority hoist cleanly — habit, not cycle breaks —
and only a handful of files actually break a cycle. (Counts and the measurement
date belong in the implementation issues, not here — MS-16-001.) Most of the
tree-wide total sits in `test/`, where a test-local import is an isolation idiom
CS-05-002 was never about.

So the rule is **enabled**, and the resolution has three parts (CS-05-002,
CS-05-005, CS-05-006):

- `per-file-ignores` carries `"test/**" = ["PLC0415"]`. Test-local imports stay.
- Every habit site in `vultron/` is hoisted.
- Every genuine cycle break in `vultron/` was baselined with a `# noqa: PLC0415`
  marker citing the issue that removes it structurally (the baseline form
  below), and #3950 removed every one by reorganization. A new deferred import
  in `vultron/` fails the gate; a new cycle is a new reorganization, not a
  marker.

A hoist that closes a cycle fails only when the cycle is entered at one
particular module, so neither pytest's collection order nor one process's import
order proves it safe. `test/architecture/test_every_module_imports_fresh.py`
(integration tier) imports every `vultron/` module as the first member of its
import cycle to load, so a hoist that closes a cycle fails there, whichever
module a deployment happens to import first. It is also how to check whether a
marker is still needed: hoist the import and run that test.

The cycles the measurement found, and how #3950 broke each. Every one but the
first closed through an eager package `__init__` re-export, never module to
module, so each fix removes the one package-level edge pointing back:

| Cycle | How it was broken |
|---|---|
| persistence ports | `CaseOutboxPersistence` importers name `core/ports/case_outbox.py` directly; `case_persistence.py` lost its PEP 562 `__getattr__` |
| publication trees ↔ call-out bundles | the publication-intent contract moved to `report/publication_intent.py` (`publish_artifact_tree.py` was never in the cycle) |
| hypercube ↔ its pattern modules | `valid_states()` and `CS_EVENT_LETTERS` moved from the hypercube to `case_states/validations.py`, which imports neither the hypercube nor the patterns |
| BT node → use-case helper (BTND-04-003) | the replica-seeding helpers moved to `core/services/case_replica_seeding.py` (BT-22-005) |
| embargo tree and nodes ↔ status/sync node packages | `EmitCaseStatusUpdateNode` moved to the shared `behaviors/case_status_snapshot.py` (BTND-04-001); `sync/__init__` stopped re-exporting the announce tree; the `close_case` effect moved from `sync/nodes` to `case/nodes`, and the embargo relay replay effects (#3915) live in `embargo/nodes/relay_effect.py` for the same reason, with `sync/nodes` naming their event type through `MessageSemantics` rather than importing it from `embargo/nodes` |
| `sync` package ↔ `case/nodes` | `sync/__init__` stopped re-exporting the reject and commit trees: `reject_tree` imports `case.nodes`, whose `actor` node commits through `sync.commit_tree`. This cycle carried no marker; the code review on #4114 found it |
| inbox pipeline ↔ use cases | the dead-letter tree left the inbox package for its own area, `behaviors/dead_letter/` (IO-02-003) |

Each was a CS-05-003 finding: a shared symbol that belongs in a neutral module
or on the side of the cycle that owns it. That is the pattern for a new one: find
the package `__init__` that makes the edge, then move the symbol, not the
import. A PEP 562 module `__getattr__` that calls `importlib` is the same
deferral in a form `PLC0415` cannot see; #4106 removed the last of those, from
`case/nodes`, and none should come back.

**`G004` (`logging-f-string`) was the other provisional exclusion in the
configuration that #3352 landed with, and that entry too was deleted, not
kept — #3991 removed it.** Its ADR-0094 row cited #3378, which asked whether the
rewrite target was lazy `%`-args or structured `extra=` fields. The answer is these
were never alternatives: the template-plus-args shape decides how the *message*
gets its values (SL-01-005), while `extra=`-style record fields are the
correlation mechanism (SL-02-003, built by #3992) and are set by a boundary
filter rather than per call. So the rule is **enabled**: #3991 rewrites every
f-string log call to a literal template with positional args and places no
marker. Ruff's `G004` fix is available only under `--preview --unsafe-fixes` and
declines a placeholder that carries a conversion or format spec (`{x!r}`,
`{x:>5}`), so the bulk is autofixed one category at a time per ADR-0094 and the
residue is hand work; either way the rewrite is bounded, and "too many to fix
now" is not a reason to exclude (above). The reasoning is in
[notes/structured-logging.md](structured-logging.md) § "Log-Call Shape: Template
Plus Lazy Arguments (SL-01-005)".

With #3991 landed, the `G004` entry is gone, the whole `G` family runs with no
`ignore` entry and no `# noqa: G00x` marker, and a new f-string log call fails
the gate. With the `PLC0415` entry gone too (#3949), **no entry in `ignore`
cites a tracking issue**: every remaining exclusion rests on one of the first
three standing reasons above. A new provisional exclusion needs a new issue, and
this section should name it.
