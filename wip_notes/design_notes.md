Observations about the message states.

- We don't really need separate ACKs for each process model.
- ActivityStreams READ(activity) is sufficient and could substitute for ACKs.
- The original design lacks a distinction between Report and Case management
- Report handling is for triage, case handling is for coordination.
- If a report is valid, you wind up creating a case from it.
- Which semantics to use for cases: ACCEPT/REJECT or FOLLOW/IGNORE?

## Future considerations

### Polling pattern for embargo selections

Going to skip the polling pattern for embargo selections for now
as it's a bit more complex and I want to get the basic patterns implemented first,
but we can add it later if we have time. I suspect that we'd want to adopt
how Mastodon does polls: <https://docs.joinmastodon.org/spec/activitypub/#Question>

### Public Key Distribution

Mastodon already has public key distribution
<https://docs.joinmastodon.org/spec/activitypub/#publicKey>
and <https://docs.joinmastodon.org/spec/security/>
