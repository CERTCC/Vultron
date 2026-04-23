# Project Idea History

Ideas that have been processed into specs, notes, or implementation plans
are archived here for traceability.

---

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

**Processed**: 2026-04-23 — design decisions captured in
`specs/configuration.md` (CFG-01 through CFG-06) and
`notes/configuration.md`.

---

## IDEA-26040903 Do not worry about backward compatibility in prototype phase

We are still squarely in a prototyping phase, and there are no outside users
of the code we are developing here. When we make changes to the codebase we do
not need to worry about backward compatibility at all. If you're making a
change, make the change all the way. Do not hedge to preserve backward
compatibility (but obviously do not break the code in a way that prevents
you from testing your changes).

**Processed**: 2026-04-23 — design decisions captured in
`specs/prototype-shortcuts.md` (PROTO-08-001 through PROTO-08-004).

---

## IDEA-26041501 Need spec to avoid compatability shims in prototype

We need a spec that is declarative about avoiding the use of compatability
shims when refactoring code. We're in prototype development mode so there
are no
external dependencies that we need to maintain downstream. When we change
something it should be complete and permanent. Search notes/ for "shim" and
you'll see where this has come up before. We just need to make it an
explicit principle in the specs. Compatibility shims are technical debt that
we do not want to take on right now.

**Processed**: 2026-04-23 — folded into IDEA-26040903 processing; design
decisions captured in `specs/prototype-shortcuts.md` (PROTO-08-001 through
PROTO-08-004).

---

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

**Processed**: 2026-04-23 — design decisions captured in
`specs/outbox.md` (OX-08-001 through OX-08-004) and `notes/outbox.md`.
