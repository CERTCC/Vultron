---
title: Spec Authoring Rules — Field Values, Lint Traps, and Coverage Gates
status: active
kind: guidance
description: >
  Mechanical rules for authoring spec YAML: the five kinds and the MS-12
  decision tree (who must obey a rule decides its kind, ADR-0134), the ruling
  that inline-object requirements are `project`, which HTTP status codes are
  `foundation` and which are `project`, splitting a spec that mixes
  kinds, what a kind change moves, and the scoping of MS-12-006;
  the enum values spec-lint accepts for `kind`, `priority` and `rel_type`; `adr:`
  versus `references:`; reading the item format off its fields (ADR-0101); the
  PR-only marker-coverage guard and the strict-xfail pattern; priority tiers
  (MS-02-003/004); the `verification_debt` ratchet (MS-10-005..009); guards that
  state a domain truth (MS-05-005); removed requirements (MS-09); audit passes
  for retiring a name or splitting a requirement; and the CASE_MANAGER-versus-
  CaseActor naming discriminator.
related_specs:
  - specs/meta-specifications.yaml
  - specs/spec-registry.yaml
  - specs/testability.yaml
  - specs/architecture.yaml (ARCH-18-004)
  - specs/actor-knowledge-model.yaml (AKM-05-003, the inline-object ruling)
  - specs/http-protocol.yaml (HTTP-03, the status-code ruling)
  - specs/inbox-endpoint.yaml (IE-07-001, IE-07-002, IE-11-001)
related_notes:
  - notes/specs-vs-adrs.md
  - notes/actor-knowledge-model.md
  - notes/documentation-strategy.md
  - notes/behavioral-conformance-specs.md
  - notes/testing-pitfalls.md
  - notes/architecture-ratchet-corpus.md
  - notes/agentic-workflow.md
  - notes/user-story-catalog.md
---

# Spec Authoring Rules — Field Values, Lint Traps, and Coverage Gates

Canonical write-ups for the mechanical spec-authoring pitfalls. `specs/AGENTS.md`
keeps the short index; whether a rule belongs in a spec at all is in
[notes/specs-vs-adrs.md](specs-vs-adrs.md). If a lint or loader failure arrives
as a traceback rather than an `[ERROR]` line, read
[`vultron/metadata/AGENTS.md`](../vultron/metadata/AGENTS.md) § "Loader Failure
Attribution" first.

---

## Field Value Enums

### Valid `kind:` Values

```text
protocol  foundation  architecture  project  process
```

`implementation` is **not** valid; spec-lint rejects the file at commit time,
and the error can read like a YAML syntax error.

#### Who must obey a rule decides its kind

Who must obey a rule decides its kind; naming code never does (MS-12-002,
[ADR-0134](../docs/adr/0134-who-must-obey-a-rule-decides-its-spec-kind.md)).
The tiers are glossed on `SpecKind` in `vultron/metadata/specs/schema.py`:

- **`protocol`** — the Vultron layer: Vultron's message forms on the wire,
  which messages are sent and when, what a receiver does given its state, and
  the state machines behind them (`RM.CLOSED` is a protocol construct).
- **`foundation`** — rules inherited from ActivityStreams 2.0, ActivityPub or
  HTTP. It carries a tag naming the standard (`as2`, `activitypub`, `http`), and
  spec-lint fails one without (MS-12-009).
- **`architecture`** — recommended structure that carries over to other
  languages but is not required for compliance (behavior trees).
- **`project`** — this codebase only: deployment choices, operating limits, how
  a receiver records what it receives, core internals.
- **`process`** — how we run this project: CI, workflow, agent conventions,
  docs standards, spec authoring.

**The ledger caveat.** The CASE_MANAGER role and case-ledger sync are
`protocol`. Do not relabel them on the grounds that a federated Vultron would
not need them; re-judge only if the protocol actually drops the CASE_MANAGER.

**Inline-object requirements are `project` unless they serve a protocol
purpose** (maintainer ruling, 2026-10-14, #4599). Forcing an object inline
instead of by reference is a shortcut of this prototype, which does not yet
dereference (AKM-05-003); it is not a Vultron rule. ActivityStreams allows either
form, and a receiver coping with both is `foundation` (SE-01-002). Split a
protocol spec that demands inline (MS-12-010): the original ID keeps which object
the message carries, its type and its meaning, worded "carried inline or by
reference"; the inline demand moves to a new `project` ID (RF-02-004 / RF-02-006).
An inline rule stays `protocol` only when inlining serves a protocol purpose the
prototype does not explain, and its rationale names that purpose: ledger snapshot
content the hash chain must cover is one (CLP-07-006). If no such purpose is
evident, ask; do not invent one.

**An HTTP status code is `foundation` only when HTTP itself defines it for the
condition** (maintainer ruling, 2026-10-14, #4529): 405 for a method the resource
does not support, 413 for a body over the limit, 400 for a request that cannot be
parsed (IE-07-001); 415, 404, 429 and 503 follow by the same rule (HTTP-03).
Where HTTP leaves the choice open, the code is this codebase's and `project`:
422 for a schema failure, 400 for an activity addressed only to other actors,
400 for a body that cannot be decrypted (HTTP-03-009, IE-07-002, ENC-03-002). A
protocol rule that names such a code keeps the receiver's behavior (refuse,
store nothing) and cites the `project` spec for the code (IE-11-001). A limit is
`project` even when exceeding it draws a `foundation` code: HTTP-02-001 holds
the 1 MB default, IE-03-003 the 413. A SHOULD in the standard that Vultron makes
a MUST is Vultron's own rule and stays `protocol` (HTTP-01-001).

#### Apply the decision tree, not the neighbouring entries

The authoritative rule is the MS-12 tree. Split a mixed spec first (MS-12-010),
then ask in MS-12-005's order and stop at the first match:

1. How the project is run? → `process` (MS-12-001)
2. Only this codebase must obey it? → `project` (MS-12-002)
3. Inherited from AS2, ActivityPub or HTTP? → `foundation`, tagged (MS-12-009)
4. Every Vultron implementation must obey it? → `protocol` (MS-12-003)
5. Otherwise, recommended structure → `architecture` (MS-12-004)

A statement that names a file path, library, class or BT node does **not** match
step 2 for that reason: reword it in protocol vocabulary, or split it. Never
relabel it. Never infer a `kind` by copying the entries around it either — that
is how the protocol corpus filled with misclassified specs carrying
`lint_suppress: [missing_story_reference]` (#2601). A spec that cannot be traced
to a user story is usually misclassified, not story-less, so suppressing the
story gate is almost never the fix; MS-12-007's PR-only growth guard fails any PR
that adds a carrier. `spec-lint` prints the live carrier total.

#### Split a spec that mixes kinds (MS-12-010)

Split along what other participants can observe. The **original ID keeps the
protocol half**, reworded implementation-neutrally; how our code does it gets a
**new `project` ID** whose `relationships:` name the original. Keeping the
original ID on the protocol half keeps its stories, markers and citations in
place, so the PR-only growth guards do not trip; the markers already on it stay
(MS-12-011). Example — default-embargo creation: other participants never
observe the intermediate Proposed state (protocol, original ID); this codebase
applies PROPOSE and ACCEPT atomically in one node (project, new ID).

#### Why MS-12-006 is scoped the way it is

MS-12-006's rationale and `vultron/metadata/specs/kind_classification.py` defer
here. Each scoping choice keeps the check off specs that are already right:

- **Only story-less specs.** A protocol spec that traces to a user story has
  shown it is protocol, and its `verification:` names a `test/` path because
  MS-10-003 and MS-15-001 oblige it. Scanning every protocol spec flagged about
  half the corpus, mostly compliant specs.
- **Only the `statement`.** Naming a test file in `verification:` says nothing
  about whether the rule is protocol content (#3943).
- **No bare `module`, `class`, `function`.** They read as domain English in
  wire requirements ("a machine-readable failure class"). The miss of a few true
  positives is the accepted blind spot.
- **Reword or split, never relabel.** A message that prescribed a kind would
  repeat the literal reading ADR-0134 rejected.
- **`foundation` is scanned too.** A foundation statement naming our code also
  says how we meet an inherited rule, so it is a mixed spec. The suppression
  code keeps its `protocol_kind_with_code_reference` name, and MS-12-008 holds
  its carriers at none.

The general lesson (#3480): **an unenforced MUST anti-advertises.** A rule at half
adoption reads as "no rule here", which is worse than one nobody has started.

#### Relabeling a `kind:` moves more than the field

- **Anchors move.** A spec renders only on its own kind's docs page (SR-09-002),
  so `specs/protocol.md#…` links dangle after a relabel. Run
  `uv run python scripts/relink_requirement_anchors.py` afterwards.
- **Verification travels with the spec (MS-10-008).** An unverified MUST-tier
  item that changes kind gains its `verification:` in the same change; its
  `verification_debt` marker names the old kind's owner and fails.
- **The suppression goes with the old kind.** `scripts/relabel_spec_kinds.py`
  applies a `{spec_id: kind}` mapping and strips `missing_story_reference`,
  preserving every other line.
- **Tests and markers stay (MS-12-011),** whatever the destination kind.
  `test_no_pr_drops_a_marker_while_changing_a_kind` in
  `test/architecture/test_spec_coverage_ratchet.py` fails a relabeled ID that
  lost every marker it had at the merge base. A relabel *into* `protocol` or
  `foundation` from another kind needs a marker in the same PR.

### Valid `priority:` Values — Underscores, Not Spaces

```text
MUST  MUST_NOT  SHOULD  SHOULD_NOT  MAY
```

MS-02-002 prose writes "MUST NOT", but the enum uses underscores; `MUST NOT`
(space) fails the registry load.

### Valid `rel_type` Values in Spec Relationships

```text
implements, supersedes, extends, depends_on, conflicts, refines,
derives_from, verifies, part_of, constrains, satisfies
```

`related_to` is **not** valid and fails at load. For a loose link, use `refines`
with a `note:`, or omit the relationship.

### Link an ADR With `adr:`, Not `references:`

`adr:` is the field spec-lint validates against ADR files and `spec-dump --adr`
walks (SR-07-017). `references:` takes free strings that nothing checks, so an
ADR named there is invisible to both. Any other unknown key fails the load
(`extra="forbid"`).

---

## Spec Item Format Is Field Presence, Not a Class You Pick

Read an item's format off its fields — `preconditions`, `steps`,
`postconditions` — never off its class (ADR-0101). Today every item, bare or
not, loads as `BehavioralSpec`, so an `isinstance` test is true of the whole
corpus; #3520 makes a bare item resolve to `StatementSpec`. Write new checks over
field presence, and test the negative directly: a fixture item with no
behavioral field is not behavioral. Do not use the `behavioral` **tag** as the
oracle; files hold behavioral items without it.

Do not flag `preconditions` without `steps`: that is the condition half of an
ECA rule, and a one-step `steps` list is the action, not a claim about order.
The reliably wrong shape is an ordered sequence flattened into `statement`
prose, which MS-05-001 forbids (#3521). An inline `(1) … (2) …` list is
sometimes genuinely unordered; dispose of that hit with `lint_suppress`, not by
inventing a sequence.

---

## Priority Tiers and Verification Debt

### A Priority Gate Names a Tier, Not a Keyword

`MUST_NOT` is as absolute as `MUST`, and `SHOULD_NOT` as strong as `SHOULD`, so a
gate that selects by priority selects a *tier* (MS-02-003). In code, ask
`spec.priority.is_must_tier` or `.tier` (MS-02-004), never
`== RFC2119Priority.MUST`; `test/metadata/specs/test_priority_tier_gate.py`
fails the literal comparison under `vultron/metadata/specs/` and `scripts/`. Its
allowlist holds SR-11-003's selector, the recorded exception, written once in
`sr_11_003_gate_applies()`.

The literal comparison fails silently: the prohibitions just drop out, as when
a verification backfill reported the protocol tier complete with most
`MUST_NOT`s unverified (#2535). Read "MUST" in a priority-scoped AC as the tier
unless it excludes the negative form *and says why*.

### An Advisory That Is Routinely True Is Not Enforcement

A per-item `[WARN]` that fires on most of the corpus is noise, and a new
instance is invisible. When you add a per-item advisory, decide up front what
happens when it is routinely true: collapse it to a count plus an opt-in
listing and mark each hit with its owning issue (the shape of MS-10-005/006), or
make it a hard error and dispose of every existing hit. Never ship it at partial
adoption.

### A Ratchet Needs an Owner and a Terminal State

The MS-10 verification rule is built so it can only end at zero:

1. **The record is per requirement, not a count.** Each unverified MUST-tier
   item carries `verification_debt: '#N'`, so verifying one edits only that item;
   a pinned count races every PR in flight (`notes/testing-pitfalls.md`). An
   item with both a marker and a `verification:` fails as stale.
2. **Each marker names an open owning issue** of its kind in
   `VERIFICATION_DEBT_OWNERS`. A PR that closes an owner while a marker still
   names it fails; an owner closed by hand is reported by the
   `verification-debt-owners` workflow and never fails the build (ARCH-18-004).
3. **Zero is terminal.** When a kind has no markers, delete its owner entry;
   a marker of that kind is then a hard error (MS-10-007). Nothing yet stops a
   new marker while an entry exists; #4200 adds that guard on the shared
   `added_since_base` helper.
4. **A relabel carries its verification with it** (MS-10-008).

A new backlog-style ratchet follows the same four rules unless it states why it
cannot.

### A Verification Clause Is a Claim About the Suite

An unbacked `verification:` clause reads exactly like a backed one. MS-10-009
requires it to name a check that exists and inspects the property the statement
asserts; its rationale lists the clauses that did not. For each clause you write
or review, ask: *if this requirement were violated, would the named check fail?*
A build, lint or type-check that never examines the constrained artifact fails
the question, and so does a test you have not opened — `mkdocs build --strict`
never sees a link a build-time block prints, so assert on the built `site/`
(`docs-links`) or the rendered string instead. MS-15-001 makes a named path
resolve and `spec-lint` resolves a named test (MS-10-010), but neither says the
test inspects the property, so open it.

Name a test the way pytest does: `file.py::Class::method`, not
`file.py::method` for a method in a class. A bare `test_<name>` is looked up in
the files and directories the clause names, so name its module when it lives
elsewhere. A `protocol` or `foundation` clause that names test files needs the
spec's marker in one of them (MS-10-011); `spec-lint --changed-since
origin/main` reports a requirement you touched that lacks it.

---

## Marker Coverage Guard

### A `protocol` or `foundation` Entry Requires a Same-PR Marker Test

Every rule an implementer must obey needs a test, whether Vultron defines it or
inherits it (SR-05-004/005, ADR-0134). The PR-only guard
`test_no_pr_adds_an_uncovered_implementer_spec`
(`test/architecture/test_spec_coverage_ratchet.py`) fails on each `protocol` or
`foundation` ID the branch adds to the uncovered set: a new spec with no marker,
removal of an ID's last `@pytest.mark.spec`, or a relabel into either kind
without one. It skips, with the reason shown, when no base ref resolves; CI
fetches full history so it always runs there. No count is committed;
`spec-coverage` prints the live total.

**Fix:** add `@pytest.mark.spec("<new-id>")` to a test in the same PR.

The story gate (SR-11-003/004) still covers `protocol` only, because stories for
inherited behavior are not written yet (#4513).

`spec-coverage` reports `protocol` and `foundation` IDs only, so an AC reading
"`spec-coverage` shows `<ID>` covered" cannot be met for any other kind. Write
it as "a test carries `@pytest.mark.spec("<ID>")`" and check with `grep`.

### Use a Strict `xfail` for Not-Yet-Implemented Specs

A new `protocol` or `foundation` spec whose behavior is not built yet still needs
a marker. Write a test asserting the behavior and mark it:

```python
@pytest.mark.xfail(strict=True, reason="SPEC-ID: <short description>. Tracked by #N.")
@pytest.mark.spec("SPEC-ID")
```

Do not add a stub class; use an existing node or assertion that fails for the
right reason. The strict xfail fails loudly once the feature lands, prompting
its removal, and `reason=` links the implementation issue.

---

## Writing Requirement Text

### A Spec States Current Understanding, Not Its Own Edit History

`rationale:` and `verification:` are read as closely as `statement:`. When a
requirement changes, reread both and delete any clause that only makes sense
against the old version, especially an example chosen for the old framing:
VM-01-004's narrated amendment read as a standing endorsement of the divergence
it described (#2982). History belongs in the ADR the `adr:` field names. Do not
describe a verification test that does not exist.

### A Guard States the Truth the Mistake Violates

When a requirement exists to stop an implementation mistake, state the domain
truth the mistake violates, in the vocabulary of its kind; put the bug in
`rationale:` and let the regression test verify the positive rule (MS-05-005).
A bare ban reads as if the mistake were a live design option, and gets only a
contrived story once the story gate covers `MUST_NOT` (#4517). Keeping only the
test is not the fix: agents read specs more often than tests.

Write "a participant's assertion about itself is about itself, not about
another actor", not "the subject of a received-side RM write MUST be the
sender" — the second is the code's correction in the code's terms. If the
requirement mixes kinds, split it (MS-12-010). A coding mistake with nothing
another participant can observe is not `protocol`, or is only a regression test.

### `protocol` Means RFC Content

`protocol` is what an RFC would contain: wire messages, the behaviors that lead
to them, and state machines (MS-12-003). TCP fixes what two implementations
exchange, not how one structures its endpoints; a MUST about an internal
endpoint is `project` however firm it reads (EP-02-004). A `verification:` path
does not make a spec `project`.

The statement still has to be code-free **as written**. A protocol rule that
spells its concept in our identifiers — a dotted enum member
(`CVDRole.CASE_OWNER`), a wire class's Python name (`as_CaseProposal`), a helper
function, the `DataLayer` — stays `protocol` and is reworded, even where
MS-12-006's token list does not flag it. Protocol vocabulary is not a codebase
reference: AS2 types and field names, shorthands (`CP`, `ET`), state notation
(`VFd···`) and bare semantic names (`INVITE_TO_EMBARGO_ON_CASE`) are fine.

### Name Which Member of a Population a Requirement Constrains

When a requirement constrains one of several similar things, name **which one**.
An RFC 2119 verb on an unnamed member is often wrong under the plainer reading,
producing a check that is vacuous or falsely rejecting:

- **Timestamps.** A `CaseLedgerEntry` carries the CASE_MANAGER's commit stamp
  and the participant's claimed `payloadSnapshot.published`; monotonicity on the
  claimed field compares unsynchronised clocks (#2824).
- **Registries.** "Unrecognized activity types" fits both the AS2 vocabulary
  (reject, 422) and the semantic pattern registry (route to `UNKNOWN`); MV-01-006
  names the registry (#3217).
- **List kinds.** Count the kind of entry a rule is about, not the whole list
  (#3207).

**Corollary — name the enforcing side of a participant obligation.** A
participant duty ("a participant MUST emit … in causal order") also says what
the *receiver* does: enforce, flag, or nothing. A group heading is not enough;
give the requirement a `note` naming the enforcing side and a `verification`
at the vantage point that can observe it (for CLP-15, a whole-scenario
`check_causal_edges`, since CLP-15-005 forbids per-assertion enforcement).

### Verify an "All-Members" Group Claim Against Each Member

A group description that asserts a property of *all* its members goes stale when
one member diverges, and then mis-specifies it normatively. Check each member
against the code before relying on the claim: MSM-03 once gave `CV`/`CF`/`CD`
the `CaseStatus` semantic when they carry participant-scoped VF/D state
(ADR-0075).

### Never Restate Counts in Cross-References

See [notes/specs-vs-adrs.md](specs-vs-adrs.md) § "Never State Unverifiable,
Drift-Prone Facts in Long-Lived Docs" (MS-16-001, MS-16-002).

---

## Removed Requirements: Never Reuse an ID, Archive the Text

A removed requirement is removed, not deprecated (MS-09-001), and its ID is
never reused (MS-09-004): CM-11-005 was reused with the opposite force, so every
citation pointed at a rule it never meant. Retire with
`uv run spec-retire <ID> --why ... --by '#N' [--replacement <ID>]` (MS-09-006):
it parks the text in `plan/retired-specs/<ID>.md`, outside agent context
(MS-09-005), writes the history entry, and lists the citations to repoint
(MS-09-003). `spec-lint` fails `deprecated:`/`superseded_by:` and a re-declared
archived ID (MS-09-007). A spec-versus-code conflict found in an implementation
PR follows [notes/agentic-workflow.md](agentic-workflow.md) § "Spec Text
Conflicts With Code", and the PR body carries `## Spec amended`.

---

## Audit Passes

### A Resolving Citation Is Not a Correct Citation — Scope `Implements:` by Topic

An existence-only traceability check cannot see a wrong-topic citation: trigger
routers once cited `TB-01-001` ("the system MUST use pytest") because the `TB`
prefix looked like a trigger spec (#3354). `TB` (Testability) requirements govern
tests, and no module under `vultron/` may cite one (SR-04-011);
`test/architecture/test_implements_citations_topic_scoped.py` fails on any
`TB-NN-NNN` under `vultron/` and checks that every router `Implements:` ID
resolves. Repointing is per-file judgment, not a prefix swap: `TRIG-02` splits by
domain, so a blind `TB-02-001` → `TRIG-02-001` mints new wrong-but-resolving
citations.

### Retiring a File or Label: Grep Specs for the Bare Name

MS-15-001 flags only path-shaped tokens, so a bare filename (`PRIORITIES.md`) or
label (`group:unscheduled`) passes silently. When retiring a file, label or
convention, grep `specs/` for the bare name as well as the path form, in every
field (#2011).

### A Grep-Corpus Guard Can Resolve Its Own Documentation

A lint check that validates spec prose against a textual scan of the source tree
(MS-15-004's `_check_phantom_symbols`) is blinded by its own prose: naming a
symbol in the check's docstring puts it back in the scanned corpus, so the guard
resolves it as live (#3022).

- Assert the negative directly: a symbol named only inside the linter's own
  source is still rejected.
- Prefer file-scoped exclusions to package-scoped ones: excluding all of
  `vultron/metadata/specs/` hid real definitions such as `SHOULD_NOT`.
- Keep the two exclusion sets distinct: the phantom-*ID* allowlist excludes only
  `test/metadata/specs`, while the *symbol* corpus also excludes `lint.py`.

### A Retired-Symbol Sweep Is Not a Substitution — Check the Shape First

A "replace `OLD` with `NEW`" AC assumes the swap preserves meaning. When the
replacement has a different data shape, find-and-replace turns a stale
requirement into a wrong one, which is worse because a wrong MUST reads as
authoritative. A mapping that became a sequence (`SEMANTIC_REGISTRY` is a list in
which every `MessageSemantics` value has an entry) inverts every statement about
*keys*, *entries* or *containment* (#3022). State the intent in the issue
("every reference names the live registry accurately"), not the mechanism.

### Parallel Spec Splits: Check Every Parent

After sub-agents split compound requirements in parallel, check that each
parent's statement was trimmed: agents often add the children and leave the
parent text unchanged. Do not trust completion reports for this task (#2393).

### Name the Authority "CASE_MANAGER", Not "CaseActor"

The authority for a case is a **role** — the participant holding
`CVDRole.CASE_MANAGER` — not a component or a fixed identity (ADR-0088).
Protocol prose names it **the CASE_MANAGER**. "CaseActor" is the concrete
prototype actor that enacts the role, and "case actor service" the endpoint that
spawns `case-actor` identities. Anything per-case in a CaseActor's *identity*
(a per-case URL derived from the case slug) is a category error: no container
registered it, so a call to it answers 404.

Applied naively, the rewrite over-reaches: a role has no URI or inbox. The
discriminator:

- **"the CASE_MANAGER"** for a single-writer authority action or property:
  commits ledger entries, writes shared EM/CS state, sets participant state at
  bootstrap, authorizes a commit.
- **"CaseActor"** for infrastructure and identity: its URI, inbox and outbox,
  self-delivery to its own inbox, its DataLayer, container or co-location,
  delegated-emit store scoping (ADR-0073), or the `case-actor` URL-shape
  anti-pattern.
- **"the actor enacting `CVDRole.CASE_MANAGER`"** when the text needs an actor
  grounded in the role, such as one that can fail a hosting test.

The trap is a requirement that reads like authority but is delivery: the
self-copy of a canonical ledger entry is the actor's plumbing, while the commit
*authorization* is the role. When in doubt on an infrastructure line, keep
`CaseActor`. A naming sweep also surfaces stale premises: check a candidate's
`refines:` and `adr:` parents agree with it, not only its wording.
