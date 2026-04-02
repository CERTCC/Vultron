# Project Ideas

## Database file for TinyDB should be configurable

The original implementation just had a fixed `mydb.json` file acting as the
TinyDB database. This is fine for a simple demo, but for real-world use, it
really needs to be configurable. Whatever solution we apply here should
carry through to how we'd specify the configuration for other adapters as
well like mongodb, etc. So this seems to argue in favor of a dedicated
configuration block in the config file for the data layer, where it
specifies not only which database adapter to use, but also the relevant
configuration details for that adapter (which will include the db file path
for TinyDB, but would include other details for other adapters).

## Config files should be YAML and loaded into a structured config object

When we have a need for config files, we should use YAML for readability and
ease of editing. We should also load the YAML config into a structured
config object using Pydantic so that we can enforce types and have a clear
schema for our configuration. Rough sketch of the workflow: Load YAML config
into a dict (`config_dict=yaml.safe_load()`), then pass that dict to a Pydantic
model (`Config.model_validate(config_dict)`) that defines the schema for our
configuration. This can also allow us to have nested configuration sections
for different components, and modularity in how we define and validate
config for different adapters or features.

## Does each participant need their own Case Actor clone to manage their copy of the case?

One of the ideas of Vultron is that each participant in a case is able to
maintain their own copy of the case object, and that the main objective of
the protocol is to ensure that thes copies are kept in sync across
participants. That said, there is a distinction between the Actors who are
long-lived entities that represent people, organizations, services, etc.
that exist outside of cases, and Participants who are wrappers around such
actors providing context within a specific case. So Actor A might be a
reporter in one case, the owner of another, and the vendor in a third. But
each case is effectively operating independently at its own pace.

We have the idea of a Case Actor being created by the receiver of a report
who then decides to create a case based on that report. But the problem at
that point is that the case creator has a case object and a case actor, but
the reporter has neither of these things. So how does the reporter get their
own copy of the case object? This seems like it could be solved by the
receiver sending the reporter a CREATE activity containing a snapshot of the
case with the reporter already included as a participant in the case, and
the case would refer to the report that the reporter sent in the first place.
So now the reporter checks their open submissions and recognizes that this
is a case based on a report that they sent, and so they create their own
case object as a copy of the one in the CREATE activity, and they establish
a link between messages having the context of that case and the case object
in their system. Subsequent messsages from the case actor about that case
would need to include a reference to the case (in the context or something)
so that the reporter actor can recognize that this message is for the case.
So a message `To:` the reporter with a `context:` of the case ID would be
routed to a dedicated case handler in the reporters system that is
responsible for maintaining the reporter's copy of the case object. This is
in essence an update-only Case Actor owned by the reporter.

The finder/reporter could check the status of their local case copy and then
emit messages back to the "primary" case actor to update the case state as
needed, and those updates need to sync back via the case actor to the local
copy. (Hint: the local case should only accept updates `AttributedTo:` the
case actor, not from other actors, even if they are participants. Later on
we'll add cryptographic identities to enforce this, but for now we can just
have the case handler log as error but otherwise ignore any messages not
from the case actor that attempt to update the case state.)

This general model needs to be extended to all case participants, in fact.
Participants have their own copy of the case object. They need a mechanism
to sync their copy from the lead case actor. They need to post updates
directly to the lead case actor. The lead case actor is responsible for  
maintaining the "source of truth" and sending out updates to the participants.

We want to avoid the complexity of each Actor having a separate inbox from
their case-clone-maintainers, though, so the existence of the case replica
handler isn't something the primary case actor even really needs to be aware
of. They're just sending updates to the actors who are participants in the
case, and those actors have enough internal logic to recognize that this
message is destined for this case and that message is destined to another,
regardless of how many cases they might be involved in at any given time.
From the outside world, the Actor is the only addressible entity, and
there's only one Case Actor per case operated by the case creator/owner.
(Who is also an actor participant in the case as well, so they too have a
local copy of the case object and are not directly writing to their own copy
either but routing their updates through the Case Actor too).
