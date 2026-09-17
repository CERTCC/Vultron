!!! warning "Open question: how do actors find each other?"

    Coordination starts with one party being able to reach another.
    An actor needs a peer's inbox address, and eventually its public key, its embargo policy, and its disclosure policy.
    Nothing in the protocol says how any of that is found.

    Discovery has two levels, and both are open.
    At the actor level, resolving a name to an actor profile is the missing step, and something WebFinger-compatible is the likely shape because it fits existing fediverse tooling and the profile record is already an ActivityStreams actor with a small number of Vultron extensions ([#1189](https://github.com/CERTCC/Vultron/issues/1189)).
    At the instance level, a voluntary public registry would let operators find each other at all, which is desirable and secondary to the peering protocol itself.

    A registry raises questions the peering protocol does not.
    Who operates one is unsettled, and a neutral foundation, a git repository, and a DNS zone are all plausible answers.
    So is whether it carries only domain names, with trust verified through DNS TXT records, or richer metadata, and how stale or offline instances are retired from it.

    Demo deployments sidestep all of this by telling every container the URL of every other container at boot (CP-08-003).
    That is a stand-in for a directory service, and it is documented as one.
