# Project Ideas

## ~~Responses to design questions in `plan/IMPLEMENTATION_NOTES.md`~~

> **Captured in**: `notes/triggerable-behaviors.md`
> "Open Design Questions" — covers trigger scope, input/output schema,
> CLI relationship, and overlap with existing handlers.

~~> 1. **Trigger scope**: Which behaviors should be triggerable via API? The
   reference docs (`rm_bt.md`, `em_bt.md`, etc.) describe multi-step
   state machines. Should each leaf behavior be a separate endpoint, or
   should higher-level orchestration be the trigger unit?

We want to be able to trigger meaningful chunks of behavior tree logic via 
an API. So for example, there is no n1eed to trigger a leaf node that just 
does a condition check. But that condition check might be part of a larger 
behavior that performs a full "unit of work" within a larger process. The 
names of the nodes often reflect some indication of what they are intended 
to do, so things that a user might want to trigger directly are usually 
going to be somewhere above a leaf node, but perhaps giving higher priority 
to implementing the ones where the branch does something meaningful or makes 
a simple decision before proceeding. So you wouldn't trigger "Report 
Management" as a full process, but you might trigger "Report Validated" 
which then flows to side effects like sending an `Accept` to the reporter, 
triggers a case creation, etc. So the right granularity is somewhere in the 
middle layers of the behavior tree, where there is a meaningful unit of work 
being done.

> 2. **Input / output schema**: What payload does a trigger endpoint accept?
   At minimum it needs the target `actor_id` and enough context to identify
   the case or report. Should it return the resulting activity, a job ID,
   or just HTTP 202?

It's going to depend on the semantics of the behavior being triggered. The 
actor is always going to be a required input (who is doing the thing?) and 
will eventually need to be authenticated and authorized. 

Nearly every action will be taking place in some context where there is 
something being acted upon or responeded to. So a "Validate Report" behavior 
needs to know which `Offer(Report)` is being acted on. A "Defer Case" 
behavior needs to know which `VulnerabilityCase` is being deferred.

Some behaviors might have parameters that are relevant to the behavior 
itself that could be passed in as part of the trigger. For example, if you are triggering a
"Prioritize Case" behavior, you might want to include data about the case 
that is relevant to the prioritization process (e.g., SSVC decision point 
value selections, CVSS vector elements, etc.) that would be used as part of the prioritization logic.

Beyond that, there 
is probably often an opening for some sort of note or content to be included 
as part of the trigger, which could be used to populate the content of an 
activity that might be generated as part of the behavior. For example, if 
you are triggering "Defer Case", you might want to include a note about why 
you are deferring the case, which would then be included in the 
`Ignore` activity that gets sent to the case (and likely relayed to other 
participants). 

> 3. **Relationship to BT-08**: `specs/behavior-tree-integration.md` BT-08-001
   says the system MAY provide a CLI interface for BT execution. The trigger
   API could serve as the canonical entry point for both HTTP and CLI
   invocation.

This is a good point, and a great idea. The more parity between the CLI and 
API interfaces, the better, as it also serves Priority 1000: Agentic AI 
readiness.

> 4. **Overlap with existing handlers**: `validate_report`, `engage_case`, and
   `defer_case` already exist as inbound message handlers. The trigger API
   would be the *outgoing* counterpart — the local actor deciding to initiate
   the behavior rather than reacting to a message.

Right. For maintainability, it might be necessary to rename some existing 
handlers to make it clear that they are receiving inbound messages rather 
than serving as generic trigger points. Naming conventions will need to be 
documented as part of the design process. Perhaps as simple as 
`handle_validate_report` vs `trigger_validate_report` or something like that.
The key is to make it clear in the name and documentation that one is an inbound
message handler and the other is a generic trigger point that could be invoked
by an API or CLI.~~

## ~~Clarify the design between API 1 and API 2~~

> **Captured in**: `notes/codebase-structure.md`
> "API Layer Architecture (Future Refactoring)"

~~We've been treating the two different APIs as if they were versions when in 
fact, they are more like layers. The V2 API is intended to be serving 
activity, pub, box, and outbox in active that level, whereas the V1 API is 
intended to provide examples, and also to provide backend services. Probably 
need to split it into three layers where there's an examples layer, a 
backend services layer, and an activitypub layer. We might want to move away 
from the "API 1" and "API 2" naming convention to something that reflects the
layered nature of the architecture more clearly. For example, we could have
- `vultron.api.examples` for the examples layer
- `vultron.api.backend` for the backend services layer
- `vultron.api.activitypub` for the ActivityPub layer
Backend would fit things like the triggerable events pieces as 
well as the database checks that the demos use.
Because we are still in prototype mode we don't really need to preserve the 
old routes for all of these things to different as long as we make sure that 
all of the tests are adapted and we do not break anything on the way.~~

## ~~Each actor may maintain their own copy of the Case object, but the CaseOwner's copy is authoritative~~

> **Captured in**: `notes/activitystreams-semantics.md`
> "Case State Update Path and CaseActor Authoritativeness"

~~If an actor updates something on a case, they should send it to the CaseActor to
update the case, and then updates can be emitted from the CaseActor to the
participants of the case. So the update path for a local cache of the case would
be
`Actor -> CaseActor -> Case is updated -> CaseActor broadcasts changes to participants -> Actor receives update -> Actor updates local cache of the case`.
Updates should be authenticated to be arriving from the CaseActor before being
treated as authoritative.~~

## ~~CVD action rules applied to Cases~~

> **Captured in**: `specs/case-management.md` (CM-07-001 through CM-07-003)
> and `specs/agentic-readiness.md` (AR-07-001, AR-07-002).

~~`docs/topics/other_uses/action_rules.md` contains a table of "cvd action rules"
that give suggestions of actions an actor in a particular role within a case
might take when a case is in a particular context. These should be made
accessible via an API so that Actors who are Participants in a Case (note that
Participant wrappers also indicate case roles) can retrieve a menu of potential
actions to take given the current state of the case overall and their particular
status. This will help to prepare the way for Agents to interact with cases for
future automation purposes.~~

## ~~Relationships between Reports, Cases, Publications, and Vulnerability records~~

> **Captured in**: `specs/case-management.md` (CM-05-001 through CM-05-007).

~~Although often thought of as a one-to-one relationship, a report might describe
more than one vulnerability.
Similarly, case owners might group reports together into a single case for
handling because maybe the reports share significant overlap in their
participant pools.
Published documents about vulnerabilities might include more than one
vulnerability in the same report. Typically a publication is done at the case
level, but it is also possible that multiple publications could arise from the
same case. Vulnerability records are usually created within the course of the
coordination process, and will follow "counting rules" like those established by
the CVE program under its guidance for CVE Numbering Authorities. So while, in
general, one report leads to one case, one vulnerability, and one publication,
the system must be able to accomodate situations where there are potentially
multiples of each.

Multiple reports may arrive from different sources about the same
vulnerabilities, and these would typically be added to a single case. Also,
during the course of coordinating a case, it may become evident that there are
multiple issues at play. These could be refined into additional reports (e.g.,
CSAF documents) that could be shared with participants, or perhaps result in
multiple vulnerability records being created.

What should be maintained is that a Case has at least one report. A case should
also associate to at least one vulnerability. Cases can have zero publications.

The original vultron documentation was not sufficiently clear on the distinction
between Reports and Cases, and does not even mention the potential for
Vulnerability Records to be distinct from both. We will need to rectify this in
the course of developing the prototype. Other coordination systems like VINCE
make this distinction by having different objects to represent reports received,
cases being handled, and vulnerability records (for identification) associated
with each through the case object. Vultron will need to do something similar.~~

## ~~Consider a standard format for describing default embargo policies as part of an Actor profile~~

> **Captured in**: `specs/embargo-policy.md` (EP-01 through EP-03) and
> `notes/do-work-behaviors.md` ("Prior Art and References (Embargo Policy)").

~~This would basically be some sort of API-accessible record associated with an
Actor that you could request and it would include the Actor ID, where their
reporting endpoint (an inbox, presumably) is, their default embargo policy (
e.g., "we expect minimum 90 days and will refuse anything less", "we will only
agree to 7 days max", "we prefer minimum 45 days but will consider shorter",
etc. See `docs/topics/process_models/em/defaults.md` for additional details on
the core concepts. The format for embargo descriptions is at present
unspecified, but there might be related work in the community (bug bounty or
vulnerability disclosure policy formalism like disclose.io that could be
relevant here.)

references:

- some earlier thoughts on disclosure policy formalism and Vultron in
  `docs/topics/other_uses/policy_formalization.md`, implementation has likely
  drifted somewhat from this initial take on it.
- <https://www.rfc-editor.org/rfc/rfc9116> describes components for
  `security.txt` files
- <https://github.com/disclose/diosts/blob/252e5b9c8375e4d368af04b7b38bdfa0395b0d34/internal/pkg/discloseio/discloseio.go>
  has a data structure for a directory of disclosure programs
- <https://github.com/disclose/dioterms/tree/master/core-terms> has example
  disclosure policy terms~~

## ~~Vulnerability Discovery Behavior is out of scope for the system~~

> **Captured in**: `notes/do-work-behaviors.md`
> "Out of Scope: Vulnerability Discovery".

~~The vulnerability discovery behavior found in `vuldisco_bt.md` is out of scope for
Vultron prototype implementation. The system does not need to discover
vulnerabilities, nor does it need to model that process. It is sufficient for
the system to receive a report of a vulnerability that has been admitted by
another actor report. Submission process is effectively the starting point for
all new interactions with reports and vulnerability cases so there is nothing to
complement in the system, even though the documentation does contain a behavior
tree for vulnerability discovery behavior~~

## ~~Future Demo Ideas~~

> **Captured in**: `plan/IMPLEMENTATION_PLAN.md` Phase PRIORITY-300
> (D5-2 through D5-5) and `plan/PRIORITIES.md` Priority 300.

~~Demos we are going to want to have in the future:

1. Two actors, a finder and vendor, running in separate containers, 
   communicating through the Vultron Protocol. Finder reports vulnerability to 
   Vendor, and Finder proposes embargo, vendor accepts report, accepts embargo 
   creates case, adds report and embargo to case, adds finder as case 
   participant, adds two vulnerabilities to the case based on the report. 
   They exchange a few messages back and forth, maybe including a draft CVE 
   record or something like that. This will be a good demo for showing the basic
    Vultron Protocol interactions and the behavior tree implementation.
2. A three-actor demo (finder, vendor, coordinator). Finder reports to 
   coordinator. Coordinator creates case, adds finder as participant. 
   Coordinator has a default embargo policy that it applies to all cases. 
   Coordinator proposes embargo to finder, finder accepts. Coordinator adds 
   embargo to case. Coordinator invites Vendor to case, vendor tentatively 
   rejects (invalidates the report) with a message back to the Coordinator 
   asking a question. The Coordinator relays the question to the Finder. 
   Finder responds to Coordinator, Coordinator replies to vendor with the 
   Finder's response. Vendor accepts the report and the embargo and becomes 
   a participant in the case. A few messages are exchanged between the three 
   actors within the context of the case, including a draft CVE record that 
   they refine together. The Vendor announces to the case that they have 
   published, which triggers a case status update reflecting public 
   awareness. Finder reports they have published as well. Then the 
   coordinator closes the case.
3. A demo in which the process initially looks like scenario 1 above and an 
   embargo is established, but 
   then the vendor realizes they need the assistance of a coordinator to get 
   more vendors engaged. They offer the coordinator the opportunity to take 
   over the case, and the coordinator accepts. The coordinator becomes the 
   new case owner, and the original finder and vendor remain participants. 
   The coordinator then invites two more vendors to the case with the 
   existing embargo. They accept and become participants. One of the added 
   vendors asks for the embargo to be extended, which triggers a discussion 
   between the participants, and they agree to extend the embargo in 
   principle. The coordinator triggers the case actor to propose a new 
   embargo with the agreed to terms. Participants agree to the new embargo. 
   They exchange a few more messages, the coordinator creates a CVE record 
   and distributes it for refinement. Coordinator and Finder announce 
   publication, followed quickly by the original vendor and the two added vendors.
   The coordinator then closes the case.
   
Each of these demos would need to show actors running in independent 
containers, communicating through the Vultron Protocol, with the CaseActor 
managing the case state and enforcing the rules around who can do what within the case.
CaseActor is probably also a "spin up on demand" container that gets 
instantiated when a case is created.~~

## ~~Notes on Per-Actor DataLayer Isolation Options~~

> **Captured in**: `notes/domain-model-separation.md`
> "Per-Actor DataLayer Isolation Options" — includes Options A, B, C
> analysis, recommendation for Option B (with multi-tenant and production
> database rationale), and dependency injection guidance.

~~In `notes/domain-model-separation.md` is a section on Per-Actor DataLayer
Isolation Options. This is commentary on that section. The underlying goal
is that Actors have to have independent state, whether or not they are
running in the same container or not. But we also need to assume that
different containers can be connected to different databases. For example, a
vulnerability disclosure provider might have a single multi-tenant
backing store that they connect to from multiple containers that provide
Actor instances for individual customers. A vendor might have their own
Vultron instance in which they operate their "Vendor Actor" along with
perhaps a pool of on-demand CaseActor containers, all connected to a
vendor-specific backing store. A coordinator might do the same. So we have
to assume that Actors are independent both in terms of their in-memory state
and their backing store. TinyDB was chosen as a simple starting point
because it was a minimal change from using in-memory dicts, but it was never
intended to be a long-term production solution. It would be fine if for
protoype demo purposes we made it so that different Actors had different
backings stores, each as a TinyDB file, but just remember that the real idea
we want is that actors are completely isolated from each other and can only
communicate through the front-end passing of ActivityStreams messages
between inboxes. This seems to rule out Option C as outlined in the notes,
since that would be in-memory only. Options A or B are both viable for the
prototype, but it seems like Option B is closer to the real long-term vision,
and something you would implement if you were using a more robust database
like MongoDB as the backing store, so it is likely the easiest to adapt in
the future when we are on the road to production.~~
 