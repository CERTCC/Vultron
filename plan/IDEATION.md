# Project Ideas

## Unify demos into a single script with CLI and dockerize

Combine separate demo modules into a single script with a command-line interface
to select which demo to run. Use `click` for the CLI API in the new demo script.
Existing demo scripts that have main() already set up can retain their 
individual invokability, but they should be refactored so that they can be 
called from the new combined demo script. Also note that, as currently 
written, each demo assumes a clean slate and may not have sufficient clean 
up logic, so some refactoring may be needed to ensure that the individual demos 
can be run in sequence without cross-demo interference.
Then dockerize this demo script and set up so that
when it gets `docker-compoose up`'d, it runs interactively to prompt you from 
within the container. The new combo demo should also have an option to run all 
demos in sequence for a full demo run. Existing individual docker containers 
for the demos should be removed once the new combo demo container is set up and 
working. 

### Unit Testing note

The unified demo script should be tested to ensure that each 
individual demo can be run successfully from the CLI, and that the full demo 
run option executes all demos in sequence without errors. The CLI and full demo 
run tests can be done with mocking or stubbing out the actual demo calls, 
since the purpose of the test is to ensure that all the individual demos are being invoked
correctly, not that the demos themselves are working correctly (those should be
tested separately in their own test modules).

### Integration Testing note

We have encountered situations where the individual 
demo tests pass when run a pytest environment, but when run inside a container 
that interacts with an `api-dev` container as its backend, they fail due to 
the individual demos failing to clean up after themselves and leaving the system
in a "dirty" state that can cause subsequent demo runs to fail. So part of the
test plan for the unified demo script should include verifying that the 
individual demos run in the container successfully. This can be treated as 
an acceptance test for the unified demo script. But it doesn't need to 
become part of the automated test suite run by pytest. It can be a manual 
test that is scripted out and kept for future reference. We don't really 
have a good place to put integration tests like this yet. You will need to 
decide where to put it and how to document it, whether it's a python script, a
shell script, a Makefile target, or something else. Presumably it would go 
into a new directory for integration tests, and that directory will have a 
README.md with instructions for how to run the test and what to expect.

## ADR for standardizing Object ID format

Create an ADR to standardize Object ID format (full-URI vs bare UUID). This is a
cross-cutting change and deserves an explicit ADR in
docs/adr/ADR-XXXX-standardize-object-ids.md.
ADR should cover chosen canonical form, migration strategy, and timeline.

## Update codebase to use full-URI IDs everywhere

Update Pydantic models and persistence helpers to ensure full-URI IDs are used
everywhere (object_to_record() / record_to_object() / DataLayer).

If any persisted data currently uses bare UUIDs, prepare a migration script or
plan (document in ADR).

## Rename case_status and participant_status fields to plural forms

Small refactor/cleanup: rename model fields (case_status → case_statuses,
participant_status → participant_statuses) and provide read-only properties for
current status. Prefer to land this with tests and/or a migration plan.

## Additional ideas (consolidated from wip_notes/more ideas.md)

### Vulnerability discovery is out of scope for the prototype
The vulnerability-discovery behavior described in `vuldisco_bt.md` is out of
scope for the Vultron prototype. The system does not need to discover
vulnerabilities or model that process. It is sufficient for the system to
receive a report of a vulnerability created or admitted by another actor.
Submission is the effective starting point for interactions with reports and
vulnerability cases, so the discovery behavior tree can remain as explanatory
material only.

### Many "do work" behaviors are not implementable inside Vultron
Steps in the "do work" branches of behavior trees often describe external,
human-driven processes. See `docs/topics/behavior_logic/do_work_bt.md`.

For the pages below consider adding a clear callout (e.g., `!!! note`)
indicating the process is notional and not intended to be fully automated.
Some primitives (state transitions, emit-message steps) could be exposed as
API actions (for example, "emit message" or "update case/participant status")
that a human or external system can invoke. Examples:

- acquire exploit: human-driven; the system may only record the result.
  See `docs/topics/behavior_logic/acquire_exploit_bt.md`.
- monitor threats: ongoing monitoring that may inject notes into cases; not a
  distinct automated process. See
  `docs/topics/behavior_logic/monitor_threats_bt.md`.
- developing fixes: out of scope — Vultron coordinates but does not develop
  fixes itself. See `docs/topics/behavior_logic/fix_dev_bt.md`.
- deployment: likewise out of scope for the same reasons as fix development.
  See `docs/topics/behavior_logic/deployment_bt.md`.

### Some "do work" behaviors are partially implementable
Certain activities can be partially supported by the application:

- ID assignment: assigning IDs to vulnerabilities could be implemented as a
  stub behavior that calls an external numbering API (if available) and then
  composes an ID record in the case. See
  `docs/topics/behavior_logic/id_assignment_bt.md`.
- Publication: publication may occur outside Vultron, but publication events
  should be represented as an application-level action that triggers state
  transitions (e.g., add PUBLIC case status, add notes, store public links).
  Treat publication as an external-triggered callable behavior the CaseActor
  can accept and record. See
  `docs/topics/behavior_logic/publication_bt.md`.

### Reporting behavior is central
Reporting ("report to others") is central to coordination. It is not fully
automatable but can be supported by flows such as inviting actors to cases and
asking them to agree to embargos before joining. The spec includes a "policy
evaluation for compatibility" step (see `reporting_bt.md` and
`docs/topics/process_models/em/working_with_others.md`) that is underspecified
and could be further developed if embargo policy descriptions are standardized.

### Consider a standard format for default embargo policies on Actor profiles
Define an API-accessible embargo-policy record tied to an Actor. It should
include the Actor ID, reporting endpoint (inbox), and default embargo
preferences (examples: "minimum 90 days; refuse less", "max 7 days",
"prefer 45 days but consider shorter"). See
`docs/topics/process_models/em/defaults.md`.

Relevant references and prior work:
- `docs/topics/other_uses/policy_formalization.md`
- RFC 9116 (security.txt): https://www.rfc-editor.org/rfc/rfc9116
- disclose.io data structure: https://github.com/disclose/diosts/...
- disclose dioterms core terms: https://github.com/disclose/dioterms/...

### Encryption and keys
Leverage ActivityPub extensions for encrypted messaging and actor public keys
where possible. Suggested behaviors:

- CaseActors generate a key pair at instantiation and share public keys with
  participants. Participants may choose to encrypt messages to the CaseActor.
- Decryption should occur upstream of dispatch/semantic-extraction so handlers
  receive already-decrypted activities.
- When CaseActors send messages to participants, decide whether to encrypt to
  each participant individually (one message per recipient) or support a single
  encrypted message for multiple recipients (this affects To/CC semantics).
- Use ActivityPub publicKey semantics as guidance (see Mastodon docs/specs).

See:
- https://docs.joinmastodon.org/spec/activitypub/#publicKey
- https://docs.joinmastodon.org/spec/security/

### Relationships: Reports, Cases, Publications, Vulnerability records
Clarify object model: reports, cases, vulnerability records, and publications
are distinct concepts and not always one-to-one:

- A report may describe multiple vulnerabilities.
- A case may group multiple reports (e.g., overlapping participants).
- A publication may include multiple vulnerabilities; multiple publications may
  arise from a single case.
- Vulnerability records are typically created during coordination and must
  follow numbering/counting rules (e.g., CVE practices).

Rules and recommendations:
- A Case must have at least one report and associate to at least one
  vulnerability. A Case may have zero publications.
- Distinguish Report objects (received reports), Case objects (cases under
  handling), and Vulnerability records (identifiers). Consider patterns used by
  systems like VINCE.

- Publication representation: If publications are present, record them in one
  of two ways depending on needs and storage policy:
  1. As reference links: add publication metadata (title, publisher, date,
     URL/DOI) using a CSAF-style reference object to the case's references so
     the case points to external publications without storing large payloads.
  2. As embedded documents: append the full publication (or an archived copy)
     to the case as a note with minimal metadata (publisher, date, source URL)
     when retaining the content inside the case is desirable.
  Choose a consistent policy (links vs embedded) and record it in the ADR or
  docs so clients and UI can render publications predictably. 
     RECOMMENDATION: use reference links to avoid storing large publications,
     but allow for future flexibility to embed if needed.

### CVD action rules applied to Cases
`docs/topics/other_uses/action_rules.md` lists suggested CVD action rules
mapping actor roles and case states to possible actions. Expose these via an
API so case participants can retrieve a menu of potential actions given the
case state and their role. This will ease agent and human interaction and
support future automation.

### Authoritative case copy and update flow
Actors may keep local copies of Case objects, but the CaseOwner's copy is
authoritative. Recommended update flow:

Actor -> CaseActor -> Case updated -> CaseActor broadcasts updates ->
Actor receives update -> Actor updates local cache.

Updates must be authenticated as coming from the CaseActor before being treated
as authoritative.

### Documentation refactoring using Diátaxis
Adopt the Diátaxis framework to reorganize docs:

- Tutorials (Learning) — runnable demos and examples.
- How-to guides — task-oriented instructions (run local server, connect bug
  trackers).
- Explanation — conceptual material.
- Reference — API and technical detail.

Tasks:
- Review docs and mkdocs.yml navigation.
- Identify gaps: misplaced content, archival candidates, living docs that need
  sync with code.
- Reorganize to Diátaxis sections.
- Write tutorials focused on runnable examples and demos (e.g., how to run
  demos; what Vultron is and isn't).
- Create How-To guides for common tasks and integrations.
