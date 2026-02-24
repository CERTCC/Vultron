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
demos in sequence for a full demo run.

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

