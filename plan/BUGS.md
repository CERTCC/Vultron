# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

You will need to run the server to reproduce these bugs.
hint: `uv run uvicorn vultron.api.main:app --host localhost --port 7999`

Note that regardless what IMPLEMENTATION_NOTES.md or tests indicate,
the fix is still considered failing until there is no logged error
when running the demo script `src/scripts/receive_report_demo.py`.
The previous fix was incomplete.
You can run this with `uv run python src/scripts/receive_report_demo.py`.

---

## FIXED 2026-02-17: Data layer GET endpoints missing subclass fields

**Status**: ✅ RESOLVED

**Issue**: Demo 1 (Validate Report) was failing with "Could not find case related to this report" even though cases were being created in the database.

**Root Cause**: FastAPI data layer GET endpoints had `-> as_Base` return type annotations, causing FastAPI to use `as_Base` as the response_model. This restricted serialization to only base class fields (as_context, as_type, as_id, name, preview, media_type), excluding all subclass-specific fields like `vulnerability_reports`, `case_participants`, `content`, etc.

**Fix Applied**:
1. Removed `-> as_Base` return type annotation from `get_object_by_key()` in `vultron/api/v2/routers/datalayer.py`
2. Removed `-> dict[str, as_Base]` return type annotation from `get_objects()` in same file
3. Updated `find_case_by_report()` in `vultron/scripts/receive_report_demo.py` to handle both string IDs and full VulnerabilityReport objects in the `vulnerability_reports` field

**Tests Added**: Created `test/api/v2/routers/test_datalayer_serialization.py` with comprehensive tests verifying:
- VulnerabilityCase includes vulnerabilityReports field
- All VulnerabilityCase-specific fields are present
- VulnerabilityReport includes content field
- Fix works for all subclass types

**Verification**: All 3 demos in `receive_report_demo.py` now pass successfully.
