---
source: TASK-CC
timestamp: '2026-05-05T14:13:04.397434+00:00'
title: 'CC.2: Reduce all CC 11-15 functions to CC<=10 and tighten gate'
type: implementation
---

## TASK-CC CC.2 — Cyclomatic Complexity Phase 2: Reduce CC 11–15 violations and tighten gate

Refactored all 24 functions that exceeded CC=10 across 14 files, reducing each
to CC≤10 by extracting focused helper functions. Lowered the flake8 gate in
`.flake8` from `max-complexity = 15` to `max-complexity = 10`, permanently
blocking future regressions at the accepted upper bound. Upgraded
`IMPLTS-07-008` in `specs/tech-stack.yaml` from SHOULD to MUST.

Files refactored:

- `vultron/adapters/driving/fastapi/main.py` (`main`)
- `vultron/adapters/driving/fastapi/outbox_handler.py` (`handle_outbox_item`)
- `vultron/adapters/driving/fastapi/routers/actors.py` (`post_actor_inbox`)
- `vultron/core/behaviors/case/nodes.py` (`CreateCaseOwnerParticipant.update`, `InitializeDefaultEmbargoNode.update`, `CreateCaseParticipantNode.update`)
- `vultron/core/behaviors/report/nodes.py` (`CreateCaseActivity.update`)
- `vultron/core/case_states/validations.py` (`is_valid_transition`)
- `vultron/core/use_cases/received/embargo.py` (`RemoveEmbargoEventFromCaseReceivedUseCase.execute`, `AcceptInviteToEmbargoOnCaseReceivedUseCase.execute`)
- `vultron/core/use_cases/received/report.py` (`SubmitReportReceivedUseCase.execute`)
- `vultron/core/use_cases/received/status.py` (`AddCaseStatusToCaseReceivedUseCase.execute`)
- `vultron/core/use_cases/triggers/embargo.py` (`SvcAcceptEmbargoUseCase.execute`, `SvcRejectEmbargoUseCase.execute`)
- `vultron/demo/scenario/multi_vendor_demo.py` (`verify_multi_vendor_case_state`)
- `vultron/demo/scenario/three_actor_demo.py` (`verify_case_actor_case_state`)
- `vultron/demo/scenario/two_actor_demo.py` (`find_case_for_offer`, `verify_vendor_case_state`)
- `vultron/metadata/history/backfill_implementation.py` (`_coerce_manifest_entry`)
- `vultron/metadata/history/cli.py` (`main`)
- `vultron/metadata/specs/llm_export.py` (`to_llm_json`)
- `vultron/metadata/specs/render.py` (`render_markdown`, `_spec_to_dict`)
- `vultron/wire/as2/extractor.py` (`ActivityPattern.match`)

Outcome: `uv run flake8 --max-complexity=10 --select=C901 vultron/ test/` produces no output.
All 2302 tests pass (10 skipped, 5633 subtests).
