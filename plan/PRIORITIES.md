# Priorities

The top priority is the Behavior Tree prototype implementation 
partially outlined in
`specs/behavior-tree-integration.md` and `plan/IMPLEMENTATION_PLAN.md`.
Phase BT-1 is complete; the next priority is Phase BT-2 (extend BT integration
to remaining report handlers). See `plan/IMPLEMENTATION_NOTES.md` for design
decisions and rationale.

BT integration from this point forwards should focus on implementing 
and integrating workflow demonstrations of the ActivityPub processes outlined in

`docs/howto/activitypub/activities`, specifically:

Higher priority:
- `docs/howto/activitypub/activities/acknowledge.md`
- `docs/howto/activitypub/activities/initialize_case.md`
- `docs/howto/activitypub/activities/initialize_participant.md`
- `docs/howto/activitypub/activities/manage_case.md`
- `docs/howto/activitypub/activities/invite_actor.md`
- `docs/howto/activitypub/activities/establish_embargo.md`
- `docs/howto/activitypub/activities/status_updates.md`
- `docs/howto/activitypub/activities/manage_embargo.md`
- `docs/howto/activitypub/activities/manage_participants.md`
Lower priority:
- `docs/howto/activitypub/activities/transfer_ownership.md`
- `docs/howto/activitypub/activities/suggest_actor.md`
- `docs/howto/activitypub/activities/error.md`

The ActivityPub processes often refer to message types that correspond to 
behavior tree nodes in the BT simulator in `vultron/bt` that will need to be 
reimplemented in the new BT implementation in `vultron/behavior`. Additional 
insights on mapping processes to semantics can also be found in the 
`ontology/vultron_*.ttl` files. Note similarities in names between the 
documentation and the behavior tree nodes, these are not accidental. 


---
The project is currently in prototype development mode, therefore requirements
that are marked as `PROD_ONLY` are temporarily a lower priority than other 
requirements.

