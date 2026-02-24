Create an ADR to standardize Object ID format (full-URI vs bare UUID). This is a
cross-cutting change and deserves an explicit ADR in
docs/adr/ADR-XXXX-standardize-object-ids.md.

ADR should cover chosen canonical form, migration strategy, and timeline.

Update Pydantic models and persistence helpers to ensure full-URI IDs are used
everywhere (object_to_record() / record_to_object() / DataLayer).

Add unit/integration tests:
Pattern matching tests for subclass-as_Actor and string-ref handling.
Round-trip persistence tests for ID canonicalization.
Regression test ensuring add_case_status_to_case appends full objects.
Tests for CreateParticipant name generation.

If any persisted data currently uses bare UUIDs, prepare a migration script or
plan (document in ADR).

Add short README describing demo_step / demo_check context managers within
vultron/scripts/ and add structured-logging tests that verify the required
structured fields are present even when human-friendly emojis are used in
message text.

Small refactor/cleanup: rename model fields (case_status → case_statuses,
participant_status → participant_statuses) and provide read-only properties for
current status. Prefer to land this with tests and/or a migration plan.