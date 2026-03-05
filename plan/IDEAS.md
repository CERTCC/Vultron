# Project Ideas

## Answers to open questions in `notes/triggerable-behaviors.md`

~~**Open Question**: Should `VulnerabilityCase` support a "redacted" view
for invited-but-not-yet-accepted participants? (blocks notify-actor design)~~

~~It seems like this might be an opportunity to introduce a subclass of
`VulnerabilityCase` called `RedactedVulnerabilityCase` that only includes the
fields that are relevant to invited-but-not-yet-accepted participants. This
would allow us to maintain the integrity of the `VulnerabilityCase` model
while still providing a way to represent the redacted view for certain participants.
There could be a `redact()` method on `VulnerabilityCase` that returns an
instance of `RedactedVulnerabilityCase` with the appropriate fields omitted
or redacted. (Not all redactions are necessarily complete omissions,
although some may be, and in those cases we'd just leave the field out
entirely.) This approach also allows us to use type hints to ensure that
redacted versions of cases appear where expected and that we don't
accidentally use a full `VulnerabilityCase` where a redacted version is required.
This will require a bit of reasoning about inheritance to get it right. It
will also imply some potential changes for activities that expect a
`VulnerabilityCase` if there are places where one should be allowed but not
the other. We will need to decide whether the ID of a redacted case is in
any way related to the ID of the full case. It seems for opsec purposes that
it would be best if they were completely unrelated. Also, the redacted case
should be unique to the invitee—that is, if the CaseActor is sending
invitations to multiple Actors, they should get different redacted case IDs
so that it's more difficult for an attacker to observe the IDs and infer the
size of the participant list. Assuming that even the redacted case is
encrypted (eventually, not in the prototype yet), then it would be very
difficult to reconstruct who was notified given that you have access to only
one redacted case ID and no information about the full case ID until the
invitee accepts the invitation and gets access to the full case.~~

> Captured in `notes/triggerable-behaviors.md` (Invitation-Ready Case Object)
> and `specs/case-management.md` CM-09-*.


~~**Open Question**: Should `CaseParticipant` track which embargo(es) a
participant has explicitly accepted? (blocks VP-05-* compliance)~~

~~Yes, this seems necessary. All participants should be on record as having
accepted the active embargoes for the case from the moment they are added as
participants. This allows the case to have complete records of which
participants are aware of which embargoes, which is important for auditing
case histories later. It seems like these acceptances should be timestamped
on receipt by the case too. (The CaseActor applies a trusted timestamp, do
not trust the timestamp claimed by the participant. We don't know when they
did what they did, we only know what time we received it.)~~

> Captured in `notes/triggerable-behaviors.md` (Per-Participant Embargo
> Acceptance Tracking) and `specs/case-management.md` CM-10-*.


~~**Open Question**: Should the `reject-report` trigger accept a mandatory
`note` field (reason required) to encourage documentation of hard-close
decisions? (blocks TB-03-003 refinement)~~

~~It seems this question is about whether the reject-report trigger in
particular needs to require a note field versus the optional note field we
already said we need for all triggerable behaviors. In this case, I think
the answer is yes, it should be required to be present (MUST). Do we require
it to be a non-empty string too? I'd say "non-empty" is a SHOULD, not a MUST.~~

~~This is probably a broader concern that just came up in the previous
paragraph: Requiring a field to be present is not the same as requiring it
to be non-empty, and schema validation in Pydantic will need to know the
difference. In general, we want to usually set the rule that "if present,
then non-empty", which implies the converse "if empty, then not present".
This will come up in places where fields are both optional and required, so
it's worth noting in the design specs that it's a common pattern that we want to
enforce: "if present, then non-empty". This will carry over from the
Pydantic models to the JSON Schemas derived from them.~~

> Captured in `specs/triggerable-behaviors.md` TB-03-004 and
> `specs/code-style.md` CS-08-001. The `reject-report` note field is now
> MUST-present, SHOULD non-empty. The broader "if present, then non-empty"
> pattern is codified as CS-08-001.