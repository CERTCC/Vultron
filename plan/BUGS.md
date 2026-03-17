# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

---

The following bugs can be grouped into a single commit since they are all
related to validation of trigger requests.

Bug: ProposeEmbargoTriggerRequest needs to validate not only that end_time
is a datetime and not none, it needs to enforce that it's a TZ-aware date time
and it is in the future. Tests are currently failing because they are not
setting the end_time at all, but we need to expand the tests to cover the
full range of validation rules for this field.
**FIXED**: Added TZ-aware + future-time validators to both HTTP model
(`ProposeEmbargoRequest`) and domain model (`ProposeEmbargoTriggerRequest`).
Made `end_time` required (not optional) in the HTTP model.

Bug: ValidateReportTriggerRequest, InvalidateReportTriggerRequest,
RejectReportTriggerRequest, and CloseReportTriggerRequest should verify that
the offer is an offer of a report, not some other type of offer.
**FIXED**: Existing `_resolve_offer_and_report()` in `report.py` already raises
`VultronValidationError(422)` when the referenced object is not an Offer of a
report. Tests added and confirmed passing.

Bug: CaseTriggerRequest should enforce that `case_id` is a valid case ID (and
that it resolves to an actual case) beyond just being a non-empty string.
**FIXED** (URI format only — DB lookup not required): Added URI scheme format
validator to `CaseTriggerRequest` in both HTTP models (`_models.py`) and
domain models (`requests.py`). Non-URI strings now return 422; valid URIs
that don't resolve to a case continue to return 404 as before.

