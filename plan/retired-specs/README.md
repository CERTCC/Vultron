# Retired Specs

One file per removed requirement ID, named `<ID>.md`, holding the text the
requirement had when it was removed (MS-09-005).
This folder is outside `specs/` on purpose: retired text is never loaded into
agent context, and an ID here is never reused (MS-09-004).
Write entries with `uv run spec-retire <ID>` (MS-09-006); `spec-lint` fails if an
ID in this folder is declared in `specs/` again (MS-09-007).
