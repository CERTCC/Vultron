!!! warning "Open question: how do actors find each other?"

    Coordination starts when one party can contact another.
    An actor needs the inbox address of a peer.
    It also needs the public key of that peer, its embargo policy, and its disclosure policy.
    The protocol does not say how an actor finds this data.

    Discovery has two levels, and the two levels are open.
    At the actor level, an actor cannot resolve a name to an actor profile.
    A WebFinger-compatible mechanism is the expected shape, because it fits existing fediverse tools ([#1189](https://github.com/CERTCC/Vultron/issues/1189)).
    The profile record is already an ActivityStreams actor with a small number of Vultron extensions.
    At the instance level, a voluntary public registry lets operators find each other at all.
    A registry is useful, but it is secondary to the peering protocol.

    A registry has questions that the peering protocol does not have.
    The operator of a registry is unsettled, and a neutral foundation, a git repository, and a DNS zone are all possible answers.
    The content is also unsettled.
    A registry can hold only domain names, with DNS TXT records as the trust anchor, or it can hold more data.
    The method to retire stale or offline instances is a third open point.

    Demo deployments do not have this problem.
    Each container receives the URL of each other container at start-up (CP-08-003).
    This is an alternative to a directory service, and the specification records it as one.
