# Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

## app.py Root Logger Side Effect (2026-02-27)

`vultron/api/v2/app.py` sets `logging.getLogger().handlers` and
`logging.getLogger().setLevel(logging.DEBUG)` at module import time. Any test
that imports `app.py` (directly or transitively) inherits a DEBUG-level root
logger with handlers that close on teardown, producing `ValueError: I/O
operation on closed file.` noise in every pytest run.

**Fix**: Move the root-logger configuration into the FastAPI `lifespan` event
handler or an explicit `configure_logging()` function called only at server
startup — never at module import time. A `conftest.py` fixture should configure
logging for tests independently.

**Cross-reference**: `notes/codebase-structure.md` "Known Issue: app.py Sets
Root Logger Level at Import Time"; `plan/BUGS.md`.

---

## CM-02-008 Vendor Initial Participant Not Verified (2026-02-27)

`specs/case-management.md` CM-02-008 requires the vendor/coordinator
(the case owner) to be recorded as the initial primary `CaseParticipant`
before any other participant is added when a `VulnerabilityCase` is created
from a `VulnerabilityReport` Offer.

A code inspection of `vultron/behaviors/case/create_tree.py` shows that
`CreateCaseActorNode` creates the `CaseActor` (an ActivityStreams Service)
but does not visibly create a `VendorParticipant`. It is unclear whether this
responsibility is handled in `create_case_participant` (a separate handler
called later in the demo sequence) or if it is genuinely absent. Task SC-1.3
is needed to verify and close this gap.

---

## Triggerable Behaviors — Design Questions (2026-02-27)

PRIORITIES.md PRIORITY 30 calls for exposing RM/EM triggerable behaviors as
API endpoints. Key open design questions before implementation:

1. **Trigger scope**: Which behaviors should be triggerable via API? The
   reference docs (`rm_bt.md`, `em_bt.md`, etc.) describe multi-step
   state machines. Should each leaf behavior be a separate endpoint, or
   should higher-level orchestration be the trigger unit?
2. **Input / output schema**: What payload does a trigger endpoint accept?
   At minimum it needs the target `actor_id` and enough context to identify
   the case or report. Should it return the resulting activity, a job ID,
   or just HTTP 202?
3. **Relationship to BT-08**: `specs/behavior-tree-integration.md` BT-08-001
   says the system MAY provide a CLI interface for BT execution. The trigger
   API could serve as the canonical entry point for both HTTP and CLI
   invocation.
4. **Overlap with existing handlers**: `validate_report`, `engage_case`, and
   `defer_case` already exist as inbound message handlers. The trigger API
   would be the *outgoing* counterpart — the local actor deciding to initiate
   the behavior rather than reacting to a message.

Recommendation: Draft a design note or ADR (P30-1) that maps each triggerable
behavior to the corresponding simulation tree in `vultron/bt/`, defines the
endpoint contract, and decides which behaviors are in scope for PRIORITY 30.

---

## Actor Independence — Shared DataLayer Architecture Risk (2026-02-27)

All actors currently share a singleton `TinyDbDataLayer` backed by a single
`mydb.json` file. This violates `CM-01-001` (actor isolation) and
`BT-09-002` (no shared blackboard state), even though demo scripts manually
sequence activities to simulate isolation.

Before implementing PRIORITY 100 (actor independence), a design decision is
needed (task ACT-1):

- **Option A**: One TinyDB file per actor (`{actor_id}.json`). Simple but
  creates many files; complicates the datalayer reset endpoint used by demos.
- **Option B**: Namespace prefix per actor inside one TinyDB file (e.g.,
  TinyDB table per `actor_id`). Keeps a single file; partitions data by actor.
- **Option C**: In-memory dict-backed DataLayer per actor (no persistence).
  Good for tests; insufficient for production or Docker demos.

The chosen design must also address how the `BackgroundTasks` inbox handler
resolves the correct per-actor DataLayer instance from the `actor_id` route
parameter.

---

## EmbargoPolicy Model Gap (2026-02-27)

`specs/embargo-policy.md` EP-01 specifies a `EmbargoPolicy` Pydantic model.
The spec is not tagged `PROD_ONLY` for the model definition (only the API
endpoint EP-02 and compatibility evaluation EP-03 are). The model should be
added as a standalone Pydantic class in `vultron/as_vocab/objects/
embargo_policy.py` as part of SPEC-COMPLIANCE-2 (tasks EP-1.1, EP-1.2)
even if the endpoint is deferred.

Note that `notes/do-work-behaviors.md` references embargo policy compatibility
evaluation as an underspecified area — the model definition is a prerequisite
for that future work.

---

## Docstrings and markdown-compatibility

We use `mkdocstrings` to render docstrings in our documentation. 
To ensure that the docstrings render properly, they must use markdown-compatible
syntax.

### Lists

Docstrings like those in `vultron/demo` MUST use markdown-compatible syntax 
for lists, including leading blank lines and consistent indentation. 

Example:

```python
"""
When run as a script, this module will:

1. Check if the API server is available
...
"""
```


### Inline code

Use backticks for inline code references in docstrings, even if they are not
actual code elements. This ensures that they render properly in the documentation.

Examples:

```python
"""
To see BT execution details, run the API server with `DEBUG` logging enabled:
  `LOG_LEVEL=DEBUG uvicorn vultron.api.main:app --port 7999`
"""
```

```python
"""
Uses `RmValidateReport` (`Accept`) activity, followed by vendor posting
a `CreateCase` activity to the finder's inbox.
"""
```

### Documentation links

When referencing other documentation in docstrings

- use proper markdown links.
- assume that the docs will share `docs/` as the site root directory.
- use relative paths to link to other markdown files.
- use the page title as the link text where possible.

Example:

```python
"""
This follows the "Receiver Accepts Offered Report" sequence diagram from
[Reporting a Vulnerability](/howto/activitypub/activities/report_vulnerability.
md).
"""
```

---

### vultron/as_vocab/examples/vocab_examples.py and vultron/scripts/vocab_examples should be refactored out

`vultron/as_vocab/examples/vocab_examples.py` was originally a single file 
containing multiple vocabulary examples that are now dispersed across 
multiple files in `vultron/as_vocab/examples`. When it was refactored, a 
shim was left behind in `vultron/scripts/vocab_examples.py` because a large 
number of API code, tests, and documentation in `docs/` referenced the old 
`scripts/vocab_examples.py` script. This made sense temporarily to avoid 
breaking references, but now that the new refactoring is in place, we should
remove the shim and update all references to point directly to the new files in
`vultron/as_vocab/examples/`. This will simplify maintenance and avoid 
confusion about where the canonical examples are located. (and avoid 
violating `CS-03-001` by using wildcard imports in the shim file) This will 
require updating all imports of vultron/scripts/vocab_examples.py and 
updating all the inline python code snippets in docs that reference the old 
script. This is a good candidate for a single large refactor commit that 
updates all the references in one go, since the change is straightforward but widespread.

---

