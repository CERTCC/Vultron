!!! warning "Open question: how do actors find each other?"

    Coordination starts when one party can contact another.
    An actor needs the inbox address of a peer.
    It also needs the public key of that peer, its embargo policy, and its disclosure policy.
    The protocol does not say how an actor finds this data.

    The problem is older than the protocol.
    An embargo divides the world into the Participants who belong in a case and everyone else, and knowing who a party is does not say why it is relevant to a case.
    Authentication is not authorization.
    In a small case the answer is a web search for the affected Vendor's disclosure contact.
    In a case with many Vendors that approach does not scale, for reasons the 2022 Vultron technical reports set out:

    - Contact information for every relevant party is slow to collect by hand.
    - Vendors accept reports through different channels, such as email, a web form, or an account on their own bug tracker, which prevents automated notification.
    - Which other Vendors' products contain an affected component is often unknown, so a case cannot follow the software supply chain.
    - A vulnerability in a protocol or a specification affects every implementation, and the implementers are hard to enumerate.
    - Some Vendors treat the components of their products as confidential, which hides that a product is affected.

    Community directories show the value of a shared answer.
    The [FIRST member list](https://www.first.org/members/teams/){:target="_blank"} and [Disclose.io](https://disclose.io/programs/){:target="_blank"} each publish disclosure contacts, and Disclose.io accepts community contributions.
    A Vendor can also publish a [`security.txt`](https://securitytxt.org){:target="_blank"} file ([RFC 9116](https://www.rfc-editor.org/rfc/rfc9116.html){:target="_blank"}) so that a Reporter finds its contact without a directory.
    Standard contact records with an interface to read them, standard contact methods, publication and aggregation of software bills of materials, and a way for Vendors to register interest in a technology would each remove one of the obstacles above.
    The last of these has a cost: an adversary, or a competitor, can register interest in a technology to receive reports about products it does not make.

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

    The reference implementation reserves the seam.
    Its behavior trees have an actor-discovery call-out ([#2469](https://github.com/CERTCC/Vultron/issues/2469)), and the backend that answers it is not built.
    Demo deployments do not have this problem.
    Each container receives the URL of each other container at start-up (CP-08).
    This is an alternative to a directory service, and the specification records it as one.
