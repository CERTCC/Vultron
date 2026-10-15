# Pre-Review Self-Check

Four checks that catch the oversights a fresh reviewer most often finds after
the push: stale text, untested branches, partial state on failure, and
duplicated code. The author runs them on the finished diff (`build` Phase 5,
`bugfix` Phase 4); the reviewer runs the same four as review prompts (`pr-triage`
Phase 8). Each item points at the rule it applies; the rule text lives there.

Every item ends in a written result. The author puts the four results in the
PR body's `## Verification` section, under `Self-check:`
(`pr-body-guide.md` § "Implementation PR rules"), drafting the body before the
pre-push review so the reviewer can read them. "None found" is a result; a
blank is not.

## The four items

1. **Affected-text sweep.** For each behavior the diff changes, and each name it
   renames or removes, search `docs/`, `notes/`, `specs/` (statement, rationale
   and `verification:`), every `AGENTS.md`, docstrings and comments for the old
   claim or name, and update every hit. Build the search set from the consumers,
   per `notes/agentic-workflow.md` § "Enumerate the Affected Set From Its
   Consumers".
   *Result:* the search terms used and the files updated, or "no hits".
2. **Failure-path pass.** For each new or changed store write, ledger commit,
   outbox write or send: what is left behind if it fails halfway, what happens
   on redelivery or retry, and the test that pins it. The established patterns
   are in `notes/bt-pitfalls.md` (partial writes, idempotency selectors, emit
   nodes that fail loudly), `notes/bt-integration.md` § "The Received-Side
   Stages (ADR-0111, ADR-0135)" (commit before effects such as an outbox
   write), `notes/outbox-delivery-reliability.md` § "A
   Response to an Inbound Activity Takes Its Id From the Request" (withdraw on
   commit failure, retry-stable ids) and `vultron/core/AGENTS.md`
   § "Idempotency Responsibility Chain".
   *Result:* one line per write — outcome on failure, outcome on retry, test —
   or "no writes changed".
3. **Branch coverage.** Every new branch has a test, failure branches included
   (`completeness-doctrine.md` § "What 'Done' Means"). A new `SvcXxxUseCase`
   has its file under `test/core/use_cases/triggers/`
   (`notes/triggers-test-coverage.md`).
   *Result:* any branch left untested, with the reason, or "every new branch
   tested".
4. **Reuse check.** Re-run the `compose-before-create.md` search against the
   finished diff: no copy-pasted bodies (CS-22-001), and every outbound activity
   built with `vultron.wire.as2.factories` rather than a raw `as_*` constructor
   (AF-01-001).
   *Result:* the helpers reused or extracted, or "no duplication found".

## As review prompts

A reviewer runs each item against the diff on its own, then compares the
author's `Self-check:` record (the PR body, or the draft body `build` hands the
pre-push review). A hit the record missed is a finding: FAIL when it is an
untested changed behavior or a write that leaves partial state, IMPROVE
otherwise. An implementation PR body with no `Self-check:` record is an
IMPROVE finding.
