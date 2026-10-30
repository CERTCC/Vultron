---
title: Demo CI Invariant Harness Design
status: active
kind: guidance
description: >
  Rules for the demo CI case-ledger invariant harness: separate demo and
  harness jobs, an artifact that exists even when the demo fails, the narrative
  causal-edge schema, harness file conventions, the per-scenario expected
  semantic types table (ratcheted), keeping DEMOMA-16 and the harness constants in
  one PR, reading a red harness job, post-merge runs on `main`, and
  cancellation-safe failure notification.
related_specs:
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
  - specs/ci-security.yaml
  - specs/case-ledger-processing.yaml
  - specs/case-management.yaml
related_notes:
  - notes/ci-workflow-authoring.md
  - notes/demo-scenario-authoring.md
  - notes/demo-scenario-registry.md
  - notes/demo-ci-scenario-coverage.md
  - notes/demo-ci-diagnostics.md
  - notes/testing-pitfalls.md
relevant_packages:
  - test/ci/invariants
  - vultron/demo/helpers
---

# Demo CI Invariant Harness Design

---

## Separate CI Job Pattern (DEMOCI-04)

Each scenario's invariant harness runs as its **own CI job**, after the demo job
(`needs: demo`), downloading the demo's case-log artifact. Do not fold the
harness back into the demo job: in one job, a demo failure masks an invariant
failure that may have a different root cause (CONCERN-1649). When both fail,
read the harness job separately.

The harness is skipped when the demo job was *cancelled*
(`needs.demo.result != 'cancelled'`, DEMOCI-04-007): a cancelled demo uploads no
artifact, so a harness under a bare `if: always()` fails at download and turns
the cancellation into a `failure`. Apply the same skip to any job that consumes
another job's artifact.

---

## Artifact Availability on Failure (DEMOCI-10)

The separate job only helps if the artifact exists when the demo fails. Every
failure path must still leave `devlogs/<demo>/dump-manifest.json` (#2239).

### Layer 1 — In-harness failures (DEMOCI-10-001 through DEMOCI-10-005)

- **`scenario_harness(demo_name)` owns the ordering**
  (`vultron/demo/helpers/harness.py`, DEMOMA-23). It resets the failure
  accumulator, always dumps the ledgers on the way out (return or any
  `BaseException`), then calls `assert_demo_success()` last. A dump error is
  recorded in the manifest's `reason` and the original exception re-raised with
  the `demo_check` failures attached (DEMOCI-10-004).
- **The dump always writes a manifest** (`dump_case_ledgers()` in
  `vultron/demo/helpers/ledger_dump.py`, from a `finally`), recording the case,
  captured-versus-target counts, and each missing actor with its reason. A
  timed-out dump records the actor's exception; a pre-run sentinel records no
  actors.
- **`load_devlogs()` fails rather than skips once a dump happened**
  (`test/ci/invariants/common.py`):

  | Downloaded artifact | Outcome |
  |---|---|
  | no `devlogs/`, or no `devlogs/<demo>/` | skip — the demo did not run |
  | `devlogs/<demo>/` with neither ledgers nor manifest | **fail** — the dump never ran |
  | no ledgers but a manifest | **fail**, quoting the manifest's account of why |
  | manifest unparseable | **fail** |
  | an entry with no `logIndex`, or a negative one | **fail**, naming every such entry |
  | ledgers present | load and check |

  There is no `-1` sentinel: `log_index()` raises, so an unplaced entry cannot
  sort first and satisfy an ordering check such as `check_causal_edges`.
- **An all-skip session exits non-zero.** pytest exits 0 when everything skips,
  which reads green with nothing checked. `_AllSkipGuard` in
  `test/ci/invariants/conftest.py` sets the exit status to 1 (DEMOCI-10-005).

### Layer 2 — Pre-harness failures (DEMOCI-10-006)

A failed health check, an import error, or a container that never starts all
exit before `scenario_harness()` runs. The demo job therefore writes a sentinel
`dump-manifest.json` (`ledgerFileCount: 0`) before the image build; a normal
run overwrites it, and an early exit leaves it for `load_devlogs()` to report.
The CI step writes the JSON inline with no vultron import, so the demo job needs
no uv setup; `write_prerun_sentinel()` in `ledger_dump.py` is the tested Python
equivalent.

---

## Narrative Causal Edges — Schema and Update-Together Rule (DEMOMA-22)

Each narrative under `docs/topics/scenarios/` carries a `causal_edges:` list in
its front matter (DEMOMA-22-004). Each entry is one causal relationship the case
ledger must show:

```yaml
causal_edges:
  - antecedent: <semantic_type>     # semanticType of the earlier ledger entry
    consequent: <semantic_type>     # semanticType of the later ledger entry
    consequent_actor: <name>     # actorName of the recorded emitter
    note: <text>                 # optional
    observable: true             # optional; false = not a ledger event
```

- **`consequent_actor` is the literal emitter** recorded on the entry. An
  activity the Case Actor emits for a participant is `case-actor` (the
  requester is in `attributedTo`, CM-24-001), so every `invite_actor_to_case`
  edge is `case-actor`, while a response carries the invitee. The tag is the
  `actorName` in the scenario's `dump-manifest.json`, which is not always the
  narrative's role name (in the handoff and extension scenarios C1 is `vendor`,
  C2 is `coordinator`, the Vendor is `vendor2`). Invariant 16 resolves an
  entry's `payloadSnapshot.actor` through the manifest's `routeKey`s; a tag that
  matches nothing fails the edge.
- **`observable: false`** marks an edge whose end is not a ledger entry (a report
  submitted to the receiver's API). Such edges are documented but not checked.
- **Invariant 16** (DEMOMA-22-005) asserts, on the case-actor's replica (the
  canonical order, ADR-0079), that each observable edge `(A, B)` has entries with
  `A` before `B`.
- **Unit-suite structural checks** in `test/ci/invariants/test_narrative_edges.py`
  run on the committed lists with synthetic ledgers: every `*-handoff` narrative
  orders `accept_case_ownership_transfer` before the new owner's
  `invite_actor_to_case`, and each `invite_actor_to_case` edge is followed by
  exactly one accept-or-reject edge from a different actor.
- **Update together (DEMOMA-22-006).** A change to a scenario's causal flow
  updates both the narrative's `causal_edges:` and, if it adds a semantic type that
  must always appear, the harness's `_XXX_EXPECTED_SEMANTIC_TYPES`. Neither check
  substitutes for the other.

An edge may name a semantic type the expected list does not require: the handoff
narratives declare `offer_case_ownership_transfer →
accept_case_ownership_transfer` (ADR-0053), while DEMOMA-16-005/006 require only
the acceptance. Requiring the offer would need the spec and harness edits to land
together (see "Keeping Spec and Code in Sync").

---

## Harness File Conventions

Each scenario has one self-contained harness,
`test/ci/invariants/test_<scenario>_invariants.py`, with no shared base class.
Copy an existing one:

1. Declare `_DEMO_NAME`, `_CHAIN_ACTORS` (devlog directory names, not docker
   service names) and `_<SCENARIO>_EXPECTED_SEMANTIC_TYPES`. A directory name is
   usually the part the actor plays, but not always: the `rccv-*` scenarios keep
   RVCV-legacy names, where `vendor` is C1, `coordinator` is C2 and `vendor2` is
   the Vendor. Read the scenario's own dump call before assuming the name is the
   part, and rename nothing here without renaming the dump with it.
2. Define a module-scoped replicas fixture calling
   `load_devlogs(demo_name=_DEMO_NAME)`.
3. Inject the universal invariants with
   `globals().update(make_universal_invariant_tests(...))` from
   `test/ci/invariants/universal_harness.py`, always passing `narrative_path` —
   omitting it silently drops Invariant 16, so
   `test_diagnostic_map_sync.py::test_every_harness_passes_a_narrative_path`
   requires it.
4. Add only scenario-specific assertions below: count checks, late-joiner
   checks, and path constraints unique to the scenario.

The universal set and its xfail state live in
`notes/demo-ci-diagnostics.md` § "Per-Invariant Diagnostic Map", which is
ratcheted against the factory; do not restate it.

The scenario→harness mapping is derived from the `@scenario(...)` name
([demo-scenario-registry](demo-scenario-registry.md), ADR-0098), and
`.github/demo-scenarios.json` is its generated projection: change the decorator
and run `uv run demo-scenarios --write`, never hand-edit the JSON.

Do not add a scenario registry to `test/ci/invariants/conftest.py`; it holds only
synthetic fixtures for unit-testing `common.py` (CONCERN-2004).

---

## Per-Scenario Expected Semantic Types (DEMOMA-16)

Each scenario's `_XXX_EXPECTED_SEMANTIC_TYPES` extends the universal types
(DEMOMA-16-001) with the phases that scenario must exercise, so a scenario-specific
phase cannot regress silently. The DEMOMA-16 requirements are normative; the
constants implement them.

### Scenario required semantic types

One row per scenario. `Scenario` is the registry's `label` in name order, `Spec`
is resolved from the spec corpus, and `Additional required` is checked against
each harness constant minus the universal block (DEMOCI-11-007). Multiplicity
annotations such as `(≥3)` belong to the count tests and are not checked.
`Universal 5` stays hand-written.

| Scenario | Spec | Universal 5 | Additional required |
|---|---|---|---|
| RCCV-extension | DEMOMA-16-010 | same | invite_actor_to_case, offer_case_participant, accept_invite_actor_to_case, accept_actor_recommendation |
| RCCV-handoff | DEMOMA-16-006 | same | invite_actor_to_case, accept_invite_actor_to_case, accept_case_ownership_transfer |
| RCV | DEMOMA-16-007 | same | invite_actor_to_case, accept_invite_actor_to_case |
| RCV embargo | DEMOMA-16-016 | same | invite_actor_to_case, accept_invite_actor_to_case, invite_to_embargo_on_case, accept_invite_to_embargo_on_case, activate_embargo_on_case, remove_embargo_event_from_case |
| RCV-reject | DEMOMA-16-011 | same | invite_actor_to_case, reject_invite_actor_to_case |
| RCVCV | DEMOMA-16-009 | same | invite_actor_to_case (≥3), offer_case_participant (≥1), accept_invite_actor_to_case (≥3), accept_actor_recommendation (≥1) |
| RCVV embargo | DEMOMA-16-017 | same | invite_actor_to_case, accept_invite_actor_to_case, invite_to_embargo_on_case, accept_invite_to_embargo_on_case, activate_embargo_on_case, remove_embargo_event_from_case |
| rv | DEMOMA-16-002 | validate_report, add_participant_status_to_participant, close_case, add_note_to_case, engage_case | (none) |
| RVCV-extension | DEMOMA-16-004 | same | invite_actor_to_case, offer_case_participant, accept_invite_actor_to_case, accept_actor_recommendation |
| RVCV-handoff | DEMOMA-16-005 | same | invite_actor_to_case, accept_invite_actor_to_case, accept_case_ownership_transfer |
| RVV | DEMOMA-16-003 | same | invite_actor_to_case, accept_invite_actor_to_case |

### Relationship to scenario-specific test functions

Invariant 5 checks that each expected type is **present**. A scenario that needs
an event **N or more times** adds a `test_XXX_<event>_at_least_N` test built on
`check_semantic_type_count`.

`check_semantic_type_count` also takes a keyword-only `max_count`. Add one where a
count above the scenario's own sends would itself be a defect that the universal
duplicate-commit check (`test_invariant_clp07_unique_payload_snapshot_ids`,
CLP-07-002) cannot see, such as a second Invite with its own activity id. RCV
pins `invite_actor_to_case` to exactly one: the Coordinator invites only the
Vendor, because the CASE_MANAGER seats the Reporter at case creation
(CM-22-002).

### Audit an invariant against the scenario before copying it

An invariant holds only on its scenario's protocol path. Before copying a check
to a new harness, check it against that scenario's participants and phases. A
check asserting "event X was observed" is a false failure where X is impossible
by design: in `rcv-reject` no Vendor joins, so the VFD `VFd` state is
unreachable, and its harness passes `check_fix_ready=False` (DEMOCI-06-001). Use
the check's parameter; do not skip the invariant.

---

## Keeping Spec and Code in Sync

When a scenario phase is added or removed, change the DEMOMA-16 requirement in
`specs/multi-actor-demo.yaml` and the harness's `_XXX_EXPECTED_SEMANTIC_TYPES` in
the **same PR** (DEMOMA-16-008). They cannot be split across a docs PR and a
later implementation PR.

`test/metadata/test_demo_scenario_artifacts.py` ratchets one direction:
`test_per_scenario_demoma_16_names_every_harness_semantic_type` fails when a harness
expects a non-universal type its requirement does not name, and
`test_democi_06_002_names_exactly_the_pr_set_semantic_types` holds DEMOCI-06-002
equal to the PR-set harnesses' types. The reverse is not checked, because some
statements name a type to exclude it (DEMOMA-16-002, DEMOMA-16-011).

---

## Reading a Red Invariant Harness Job

**A red `<scenario> Invariant Harness` job is not evidence that an invariant was
violated, or even evaluated.** Open the log and find the failing step first
(CONCERN-2243):

| Job outcome | What happened | What it says about invariants |
|---|---|---|
| Red at `Download case log JSONL files` | No artifact was uploaded; **pytest never ran** | Nothing |
| Red at `Run case-ledger invariant harness` | An assertion failed | A real invariant result |
| Red at `Run case-ledger invariant harness`, every test skipped | No ledgers under `devlogs/<scenario>/`; `_AllSkipGuard` forced exit 1 | Nothing — vacuous red |

### `engage_case` is universal, not scenario-specific

`engage_case` is the fifth universal type (DEMOMA-16-001) and appears in every
expected list. It is emitted from the shared helpers, so grepping one scenario
file finds nothing:

- `run_direct_path_rm_triage()` (`vultron/demo/helpers/workflow.py`) calls
  `receiver_engages_case()` for the direct receiver in every multi-actor
  scenario;
- `run_invite_path_rm_triage()` calls it for an invitee whose invite is accepted
  (CM-11-002) — not in `rcv-reject`, whose Vendor rejects;
- `rv_demo.py` calls it through `vendor_engages_case()`.

The `rvcv-handoff` `check_semantic_type_count(..., "engage_case", min_count=2)`
stays scenario-specific: it asserts the count Vendor2's post-join triage implies.

---

## Post-Merge Validation on `main` (DEMOCI-05)

`demo-integration.yml` also runs on `push` to `main`, with the same path filter
as `pull_request` (DEMOCI-05-001). A PR run validates only the ephemeral merge
commit, so two PRs each green alone can break `main` with nothing re-running
against the merged head (CONCERN-1859).

- **`push`, not cron.** A cron leaves a blind window, runs when nothing merged,
  and blames a commit range instead of one commit. Cost is bounded by the path
  filter and the concurrency group.
- **Concurrency (DEMOCI-02-011, DEMOCI-05-002).** `cancel-in-progress: true` on
  every trigger, grouped by `${{ github.workflow }}-${{ github.ref }}`. The
  `.github/actions/debounce-main-push` step at the start of the `scenarios` job
  sleeps on `push` to `main` only, so in a burst of merges only the last pays for
  the full suite. A time-range bisect across a batch is enough to find a
  regression.
- **No build cache (DEMOCI-02-007).** The GHA cache tokens are injected only into
  `uses:` steps, not `run:` steps, so `docker buildx bake --set
  "*.cache-to=type=gha"` in a composite action's `run:` step cannot reach the
  backend (#2248). Every job builds from scratch.
- **No merge queue; a combined-merge break is caught here, red.** Two PRs green
  in isolation can still break `main` together. PAD-18-009 re-tests a PR whose
  files `main` also changed, and PR-only growth guards replaced the racing count
  ceilings (#4315). The remaining gap is accepted because it fired zero times in
  about 190 merges after those rules landed (#1863, set aside). Reopen #1863 if
  semantic-conflict episodes exceed one per 100 merges over a month (#5403).

---

## CI Failure Notification — `notify-failure` Composite Action (CISEC-05)

Every push-to-`main` or scheduled workflow wires `.github/actions/notify-failure`
once with `mode: notify` and once with `mode: close` (ADR-0055), both in one job.
A single-job workflow keys them on `failure()` and `success()`; a workflow with
several jobs runs them in a final `notify` job that `needs:` every other job and
keys on `needs.*.result` (CISEC-05-012, CISEC-05-013).
`test/ci/test_workflow_failure_notification.py` enforces the wiring. The wiring
rule is in [ci-workflow-authoring](ci-workflow-authoring.md).

- **Deduplication.** The action finds an open issue carrying both
  `ci:main-failure` and the workflow-specific label: `notify` comments on it or
  opens one, `close` closes it.
- **The `ci:main-failure` label is bot-managed** (CISEC-05-005). A separate
  `issues: labeled` workflow strips it when a human applies it, so nobody can
  spoof or suppress a failure notification.

### Cancellation Safety (CISEC-05-006)

A run cancelled by the concurrency group is not a failure on that ground alone,
but a genuine failure observed before the cancellation still files
(CISEC-05-014, #3294).

- A step keyed on **`failure()`** is already safe: it is false on cancellation.
- A step keyed on **`needs.*.result`** uses `contains(needs.*.result,
  'failure')` alone (CISEC-05-015). Never add
  `|| contains(needs.*.result, 'cancelled')`, and
  never add `&& !contains(needs.*.result, 'cancelled')`: the exclusion cannot
  tell a laundered failure from a real one, so it suppresses a real failure
  whenever a newer push cancels a sibling job afterwards.
- Close the laundering path at its source instead: skip artifact-consuming jobs
  when their producer was cancelled (see "Separate CI Job Pattern";
  CISEC-05-016).
- **Only the `close` step keeps a cancellation exclusion**, because a superseded
  run must not declare recovery either (CISEC-05-009,
  `test_close_step_does_not_close_on_cancellation`).

---

## Keeping the Per-Scenario Dump Phase Thin (DEMOMA-23-002)

A scenario's `_phase_dump_case_ledgers` builds `LedgerDumpTarget`s and delegates
to `vultron.demo.helpers.ledger_dump.dump_case_ledgers()`. It MUST NOT carry its
own fetch/write loop, or one scenario's dump fix fails to reach the others
(DEMOMA-17-001).

- **Register the dump the moment a case exists**: right after the phase that
  creates it, call `harness.dump_with(lambda: _phase_dump_case_ledgers(...))`, so
  every later phase can fail without losing the ledgers (DEMOMA-23-003).
- **Do not add `try/finally: assert_demo_success()` to `main()`.** The harness
  owns the accumulator; a second owner asserts before the dump runs
  (DEMOMA-23-001).

To test it, make a mid-scenario phase raise with `DEVLOGS_DIR` at a `tmp_path`
and assert the manifest exists, as
`test/demo/test_issue_2239_ledger_dump_in_finally.py` does.
