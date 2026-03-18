# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

**FIXED** — Classes in the `vultron/core/models` folder have been modified to
use a more robust inheritance pattern that parallels the one found in
`vultron/wire/as2/vocab/base`. The core models have also been tightened up to
remove ambiguity about some required fields that were previously optional. This
was causing numerous tests to fail due to missing required fields.

Root causes fixed:
- Added `ConfigDict(populate_by_name=True)` to `VultronBase` so alias fields
  (`as_type`, etc.) can be set by Python name.
- Made `VultronActivity.as_type` required; added `actor`, `as_object` (aliased
  `"object"`), `target`, `origin` fields.
- Changed `VultronOffer`, `VultronAccept`, `VultronCreateCaseActivity` to
  inherit from `VultronActivity` (restoring the activity fields required for
  DataLayer round-trip via the wire vocabulary).
- Made `VultronParticipantStatus.context` required.
- Changed `VultronCase.case_statuses` `default_factory` to `list`, with a
  `model_validator` that initialises an initial `VultronCaseStatus` when
  `attributed_to` is set and the list is empty.
- Updated `extractor.py` to fall back to the activity-level `context` and
  `target` fields when building `VultronEmbargoEvent`, ensuring the required
  `context` is always populated.
- Fixed tests and fixtures to use valid (non-empty, non-None where required)
  field values.

All 966 tests now pass.

---