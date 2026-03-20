## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Add new items below this line

---

### 2026-03-20: IMPLEMENTATION_NOTES.md reset

This file was reset after extracting durable content into `notes/` files.
Items extracted:

- Wire-layer terminology leaking into core event interfaces →
  `notes/domain-model-separation.md`
- Core should reliably get domain objects from DataLayer →
  `notes/domain-model-separation.md`
- Datalayer storage records rethink →
  `notes/domain-model-separation.md`
- Vocabulary registry entanglement →
  `notes/domain-model-separation.md`
- Trigger services relocation plan →
  `notes/codebase-structure.md`
- VCR-019a bulk-rename lessons learned →
  `notes/codebase-structure.md`
- VCR-019d / transitions sweep → captured as TECHDEBT-34 in plan
- VCR-019e / MessageTypes clarification → implemented (complete)
- VCR-022 vs TECHDEBT-16 → confirmed identical, both complete
- Prefer `TypeHint | None` over `Optional[TypeHint]` → style preference,
  apply opportunistically during refactoring (no bulk task needed)
- VCR-005 follow-up (profile endpoint returns links only) → TECHDEBT-29
- Semantic field naming in core events → TECHDEBT-30
- `wire` needs pydantic field aliases, `core` does not → already in AGENTS.md
- `transitions` + Pydantic integration pattern → captured in
  `notes/state-machine-findings.md` (OPP-06 implementation note)

---

### Current open items (2026-03-20)

**P90-1** — Persist initial RM report-phase state in `VultronParticipantStatus`
(currently `set_status()` writes to the in-memory STATUS dict only). This is
ADR-0013 implementation step 1. `CreateReportReceivedUseCase` and
`SubmitReportReceivedUseCase` need to also create a persisted
`VultronParticipantStatus` with `rm_state=RM.RECEIVED` after storing the
report.

**P90-4** — Once P90-1 is done, the transient STATUS dict and its helpers
(`ReportStatus`, `set_status()`, `get_status_layer()`) in
`vultron/core/models/status.py` can be deprecated and removed.

**TECHDEBT-31** — `vultron/api/v2/backend/trigger_services/` is the last
significant chunk of the old `api/v2/` layer. Move its contents into
`vultron/adapters/driving/fastapi/` (see `notes/codebase-structure.md` for
the full plan). Do this before ACT-2 to avoid threading DataLayer isolation
changes through two layers.

**TECHDEBT-32** — Research the core/DataLayer boundary coupling
(object_to_record, record_to_object, vocabulary registry entanglement) before
implementing ACT-2, so that the DataLayer isolation work starts with a clean
understanding of the port contract.

**VCR-014** — `vultron/api/v2/data/actor_io.py` is the last blocker to
removing `vultron/api/v2/data/` entirely. Resolution is defined in ADR-0012
(migrate inbox/outbox into per-actor DataLayer as part of ACT-2).
