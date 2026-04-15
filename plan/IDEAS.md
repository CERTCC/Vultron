# Project Ideas

## IDEA-260301-01 Database file for TinyDB should be configurable

relevant on or after commit: 2ff533e26f994b8308f30b74d991dedbfcebfa1e

The original implementation just had a fixed `mydb.json` file acting as the
TinyDB database. This is fine for a simple demo, but for real-world use, it
really needs to be configurable. Whatever solution we apply here should
carry through to how we'd specify the configuration for other adapters as
well like mongodb, etc. So this seems to argue in favor of a dedicated
configuration block in the config file for the data layer, where it
specifies not only which database adapter to use, but also the relevant
configuration details for that adapter (which will include the db file path
for TinyDB, but would include other details for other adapters).

## IDEA-260402-01 Config files should be YAML and loaded into a structured config object

relevant on or after commit: 3fdbfa96155d87d716027c5d3a1fb929d0968b28

When we have a need for config files, we should use YAML for readability and
ease of editing. We should also load the YAML config into a structured
config object using Pydantic so that we can enforce types and have a clear
schema for our configuration. Rough sketch of the workflow: Load YAML config
into a dict (`config_dict=yaml.safe_load()`), then pass that dict to a Pydantic
model (`Config.model_validate(config_dict)`) that defines the schema for our
configuration. This can also allow us to have nested configuration sections
for different components, and modularity in how we define and validate
config for different adapters or features.

## IDEA-260402-02 Does each participant need their own stub Case Actor clone to manage their copy of the case?

relevant on or after commit: d2d2e3b5c285c9af66fad717697e9795707d2978

One of the ideas of Vultron is that each participant in a case is able to
maintain their own copy of the case object, and that the main objective of
the protocol is to ensure that thes copies are kept in sync across
participants. That said, there is a distinction between the Actors who are
long-lived entities that represent people, organizations, services, etc.
that exist outside of cases, and Participants who are wrappers around such
actors providing context within a specific case. So Actor A might be a
reporter in one case, the owner of another, and the vendor in a third. But
each case is effectively operating independently at its own pace.

We have the idea of a Case Actor being created by the receiver of a report
who then decides to create a case based on that report. But the problem at
that point is that the case creator has a case object and a case actor, but
the reporter has neither of these things. So how does the reporter get their
own copy of the case object? This seems like it could be solved by the
receiver sending the reporter a CREATE activity containing a snapshot of the
case with the reporter already included as a participant in the case, and
the case would refer to the report that the reporter sent in the first place.
So now the reporter checks their open submissions and recognizes that this
is a case based on a report that they sent, and so they create their own
case object as a copy of the one in the CREATE activity, and they establish
a link between messages having the context of that case and the case object
in their system. Subsequent messsages from the case actor about that case
would need to include a reference to the case (in the context or something)
so that the reporter actor can recognize that this message is for the case.
So a message `To:` the reporter with a `context:` of the case ID would be
routed to a dedicated case handler in the reporters system that is
responsible for maintaining the reporter's copy of the case object. This is
in essence an update-only Case Actor owned by the reporter.

The finder/reporter could check the status of their local case copy and then
emit messages back to the "primary" case actor to update the case state as
needed, and those updates need to sync back via the case actor to the local
copy. (Hint: the local case should only accept updates `AttributedTo:` the
case actor, not from other actors, even if they are participants. Later on
we'll add cryptographic identities to enforce this, but for now we can just
have the case handler log as error but otherwise ignore any messages not
from the case actor that attempt to update the case state.)

This general model needs to be extended to all case participants, in fact.
Participants have their own copy of the case object. They need a mechanism
to sync their copy from the lead case actor. They need to post updates
directly to the lead case actor. The lead case actor is responsible for  
maintaining the "source of truth" and sending out updates to the participants.

We want to avoid the complexity of each Actor having a separate inbox from
their case-clone-maintainers, though, so the existence of the case replica
handler isn't something the primary case actor even really needs to be aware
of. They're just sending updates to the actors who are participants in the
case, and those actors have enough internal logic to recognize that this
message is destined for this case and that message is destined to another,
regardless of how many cases they might be involved in at any given time.
From the outside world, the Actor is the only addressible entity, and
there's only one Case Actor per case operated by the case creator/owner.
(Who is also an actor participant in the case as well, so they too have a
local copy of the case object and are not directly writing to their own copy
either but routing their updates through the Case Actor too).

## IDEA-26040901 TinyDB data layout might not make sense ~~SUPERSEDED~~

> **Superseded by IDEA-26040902 / Priority 325.** The single-table polymorphic
> SQLModel storage model (`VultronObjectRecord`) resolves the per-type table
> question automatically — there is only one table. No standalone task needed.

Early on a decision was made to use a TinyDB table per activity type. This
may not be the best way to structure the data. We should consider whether to
consolidate into a single Activity table and just filter searches by the
type field.

## IDEA-26040902 Try a different datalayer altogether ✅ PLANNED

> **Addressed by**: Priority 325 tasks DL-SQLITE-ADR through DL-SQLITE-5 in
> `plan/IMPLEMENTATION_PLAN.md`. Must complete before D5-7-HUMAN (Priority 330).

Using SQLModel backed by SQLite is a materially stronger choice than TinyDB
for persisting Pydantic models because it eliminates the artificial boundary
between validation and storage. SQLModel composes Pydantic with SQLAlchemy, so
your domain models are simultaneously type-checked objects and durable database
rows. That means no manual serialization/deserialization layer, no ad hoc schema
enforcement, and no risk of silent data drift—your persistence layer inherits
transactional guarantees, indexing, and query semantics directly from SQLite
while remaining idiomatic to your existing Pydantic-based architecture.

By contrast, TinyDB is effectively a JSON file with a query veneer: it has no
intrinsic schema awareness, limited concurrency safety, and pushes
responsibility for validation and evolution back onto application code. In
practice, this recreates the very boilerplate you’re trying to avoid while
introducing long-term risks around data integrity and migrations. SQLModel
avoids those failure modes by giving you a principled, declarative model that
scales from local prototyping to production without changing abstractions,
making it a more durable and maintainable foundation for object persistence.

### Additional evidence from BUG-2026041001 (April 2026)

Debugging this bug made the TinyDB performance problem concrete and measurable:
**TinyDB re-reads and rewrites the entire JSON file on every single read and
write operation.** As the number of objects in the database grows across
hundreds of tests, the I/O cost compounds multiplicatively — not linearly.
The symptom was a test suite that grew from ~13 seconds to **over 15 minutes**
as test coverage expanded.

The fix required a non-trivial, test-infrastructure-only workaround: a
`pytest_configure` hook that monkey-patches `TinyDbDataLayer.__init__` to
force `MemoryStorage` globally, plus a layered autouse fixture to restore the
original init for integration tests and to re-apply the patch after any
`importlib.reload()` calls. This is significant accidental complexity —
infrastructure cost paid entirely to work around a fundamental limitation of
TinyDB's storage model, not to test any application behavior.

Key takeaways relevant to the migration decision:

- **The `MemoryStorage` workaround is a canary**: switching to in-memory
  storage reduces the suite from 15+ minutes to 13 seconds. That confirms
  TinyDB's disk I/O is the dominant cost — not application logic or fixture
  overhead.
- **The patch complexity will grow**: every future integration test that
  touches real storage needs to opt out of the global patch. The fixture
  protocol already has two layers of fragility and breaks around
  `importlib.reload()`.
- **No equivalent problem exists with SQLite**: SQLite's WAL mode and
  row-level access mean read/write cost is proportional to the *query*, not
  the *total database size*. Test isolation via transactions (rollback after
  each test) is idiomatic and requires no patching of application code.
- **The `DataLayer` port makes migration tractable**: the hexagonal
  architecture's `DataLayer` Protocol already abstracts all persistence
  operations. A SQLModel adapter can be written to the same interface and
  swapped in by changing one factory function, with no changes to any use case
  or handler.

## IDEA-26040903 Do not worry about backward compatibility in prototype phase

We are still squarely in a prototyping phase, and there are no outside users
of the code we are developing here. When we make changes to the codebase we do
not need to worry about backward compatibility at all. If you're making a
change, make the change all the way. Do not hedge to preserve backward
compatibility (but obviously do not break the code in a way that prevents
you from testing your changes).

## IDEA-26041001 Outbox posting must have `to:` field requirement

The fact that D5-7-TRIGNOTIFY-1 even had to be a task is an indicator that
we are missing a requirement: Only activities can be posted to an outbox.
And activities must have a `to:` field. We are not supporting `bto:` or
`cc:` or `bcc:`, and so far we are assuming that all Vultron exchanges are
DMs. There
are no public messages (which in ActivityPub would be an Activity lacking a
`to:`). So we should make it a requirement (or two) that only activities
with a `to:` field can be posted an outbox, and this should be on the outbox
port itself as an acceptance criteria that raises an exception when violated.

## IDEA-26041002 Default embargo should result in `EM.ACTIVE` not `EM.PROPOSED`

Contrary to what was implemented in `D5-7-EMSTATE-1`, when a default embargo
is applied to a newly created case, the resulting embargo state should be
`EM.ACTIVE`, not `EM.PROPOSED`. The rationale for this is that if the
reporter did not request otherwise, then the submission of the report signals
the reporter tacitly accepting the receiver's default embargo. So when a
case is created and a default embargo is applied, the embargo can be
considered to be active immediately. The reporter can always propose a
revision later if desired, but we don't want to leave the case in a limbo
state of `EM.PROPOSED`, which would imply that *no embargo exists* until the
reporter explicitly accepts the default embargo. See  
`docs/topics/process_models/em/defaults.md` for more discussion.

## IDEA-26041003 Differentiate between "demo" triggers and "normal" triggers

Some of the triggerable behaviors we have implemented only exist because we
need them to initiate events for the demos. They are not general purpose
triggers that we would expect to be used in the normal course of operations.
For example, an "Add(Note) to case" trigger is really specific to our demo.
But an "Add(object) to case" might be a more general trigger that could be
used for other purposes in the future. So when we are adding specific
triggers for demo purposes, we should consider whether they are exclusively
demo-centric triggers or if there is a generalized version that would be
worth implementing. If so, we should implement the generalized one, and
have the demo just use that with its specific object types or needs.

## IDEA-26041004 Use behavior trees for behaviors ✅ ADDRESSED

> **Addressed by**: D5-7-BTFIX-1 and D5-7-BTFIX-2 (new Priority 320 items
> in `plan/IMPLEMENTATION_PLAN.md`), plus documentation updates to
> `specs/behavior-tree-integration.md` (BT-06-001 through BT-06-006),
> `notes/canonical-bt-reference.md` (NEW), `notes/bt-integration.md`,
> `notes/use-case-behavior-trees.md`, `notes/protocol-event-cascades.md`,
> `notes/bt-fuzzer-nodes.md`, `notes/triggerable-behaviors.md`, and
> `AGENTS.md`. The "When to Use BTs vs. Procedural" decision table has been
> removed from all documents; the mandatory principle now reads: "All
> protocol-significant behavior MUST be BT nodes or subtrees."

The implementation of D5-7-AUTOENG-2 violates the intent that the autoengage
process should be implemented as a behavior tree structure attached to the
BT validation structure. There needs to be a `priority check` node that
returns `success`, `failure` or `running`. Semantics as follows: success
means proceed with engagement behavior (which should be a behavior sequence).
`failure` means `defer` (which is a behavior that moves the case to `RM.
DEFERRED` and emits events as appropriate), `running` means the evaluation
has not completed. The default node for the priority check can just return
success to perform the default engage on valid behavior. But we need to have
the structure in place because later on this becomes a connection point for
more complex prioritization rules (like an SSVC evaluator tree).

General observation: don't chain behavior trees with procedural stuff. Use
behavior trees. If that means wrapping a procedure in a node, so be it. That
lets us construct and reconfigure the behavior tree to reflect the desired
behavior logic without worrying about side effects that happen outside the tree.

## IDEA-26041501 Need spec to avoid compatability shims in prototype

We need a spec that is declarative about avoiding the use of compatability
shims when refactoring code. We're in prototype development mode so there
are no
external dependencies that we need to maintain downstream. When we change
something it should be complete and permanent. Search notes/ for "shim" and
you'll see where this has come up before. We just need to make it an
explicit principle in the specs. Compatibility shims are technical debt that
we do not want to take on right now.
