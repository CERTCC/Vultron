## 1. Introduction [I]

### 1.1 Background and Motivation

A vulnerability divides the world into two sets: those who know about it, and
those who do not. From the moment of discovery, every party in the knowing set
repeatedly answers two questions. What should it do next, and who else needs to
know what, and when? Coordinated Vulnerability Disclosure (CVD) continues until
the answers are "nothing" and "nobody".

Multi-Party CVD (MPCVD) is CVD involving three or more independent organizations
with different interests and roles. The shapes vary. A reporter may go to one
vendor, which discovers that other vendors ship the same component. A reporter may
go to a coordinator, which finds and notifies the affected vendors. A reporter may
go to a vendor and a coordinator at once. What the cases have in common is that
the set of participants grows after coordination has begun, each vendor works to
its own timeline, and the parties must agree when disclosure happens.

Each of those organizations usually already runs its own vulnerability tracking
system. The coordination problem is therefore not only one of people talking to
each other; it is one of separate systems needing to stay consistent about a
shared case. That is the problem Vultron addresses.

Email carries the content of a CVD case but records none of its state. No
participant can see which vendors have read the report, which have agreed to an
embargo, or in what order events occurred. Adding a party mid-case means
re-sending the history by hand, and nothing detects the gap if that fails. Vultron
gives each of these an explicit, machine-checkable representation: report status
per participant ([§6](index.md#6-report-management-rm-state-machine-n)), embargo
agreement per participant
([§9](index.md#9-participant-embargo-consent-pec-state-machine-n)), and an ordered
case ledger that every participant replicates
([§5.4](index.md#54-addressing-and-channels)).

Embargo timing is worth noting early. In practice the first two parties to a case
establish the initial embargo, and it carries forward as further participants join
and agree to it. Establishing terms early is generally easier than negotiating
them once many parties are already involved.

The protocol tracks coordination state across four dimensions: the report
lifecycle (RM), the embargo (EM), what is known about the vulnerability (CS), and
each participant's agreement to the embargo (PEC). Because CS is a compound of two
independent axes, an implementation runs five state machines
([§3.3](index.md#33-tracking-dimensions)). Messages are ActivityStreams 2.0
Activities delivered over HTTP. Delivery is asynchronous: no exchange requires both
parties to be available at the same moment.

!!! info "Who this specification is for"
    This specification is written for implementers building software that takes
    part in Vultron cases, and for reviewers assessing whether an implementation
    conforms.

    It assumes familiarity with coordinated vulnerability disclosure as a
    practice — reporters, vendors, coordinators, embargoes, CVE IDs. It does not
    assume prior knowledge of Vultron. Where it relies on an external
    specification, it says so and cites it
    ([§1.3](index.md#13-relationship-to-existing-standards)).

!!! info "See also"
    - [CVD as a Coordination Problem](../../topics/background/cvd-coordination-problem.md)
    - [What Does Success Mean in CVD?](../../topics/background/cvd_success.md)
    - [The Need for Interoperability](../../topics/background/interoperability.md)
    - [CERT Guide to Coordinated Vulnerability Disclosure](https://certcc.github.io/CERT-Guide-to-CVD)

### 1.2 Design Goals

**Actor-local state.** Each participant keeps its own replica of the case,
assembled from the messages it has received. A participant is the authority on its
own report and fix status. What the case as a whole asserts — its embargo state
and what is publicly known — has a single writer, the participant holding the
Case Manager role, so that concurrent claims resolve to one answer
([§5.4.1](index.md#541-single-writer-authority)).

**Coordination is scoped to a case, not to a system.** The Case Manager role is
held per case, and different cases may be managed by different actors. The
protocol does not require every case to pass through one shared service. It does
require, within a case, that shared state have one writer.

!!! note "Informative: how centralized is this?"
    Two readings should both be avoided.

    Vultron does **not** require a single central authority holding all cases. Any
    actor able to satisfy the Case Manager role can manage a case, and the role is
    transferable ([§11.3](index.md#113-case-ownership-transfer-n)).

    Equally, Vultron as it stands is **not** a fully decentralized design. Within
    a case there is one writer, and its availability bounds how fast the case can
    progress. The current reference implementation goes further and runs a
    dedicated service actor per case.

    The protocol leaves more distributed realizations open — a shared ledger
    among peers, for instance — and this version does not specify one
    ([§5.4.2](index.md#542-routing-topology)).

**Asynchronous, message-driven coordination.** Participants announce their own
transitions rather than being polled, and no exchange requires two parties to be
online at once. A participant that is temporarily unreachable does not block the
others from making progress.

**Extensible role model.** Roles are not exclusive: a participant may hold
Reporter, Vendor and Coordinator at the same time
([§3.5](index.md#35-participants-and-roles)). Roles that confer protocol authority
are kept separate from roles that describe what an actor does in the world, so the
two can vary independently.

**Interoperable wire format.** ActivityStreams 2.0 is the normative wire
vocabulary. Reusing an established open standard means the message format is
already specified and already understood, and it leaves ActivityPub-based delivery
available as a path to potentially compatible tooling. Vultron has not yet been
integrated with the wider ActivityPub ecosystem.

### 1.3 Relationship to Existing Standards

**ActivityStreams 2.0 and ActivityPub.** Vultron uses the ActivityStreams 2.0
vocabulary as its wire format, and ActivityPub HTTP delivery is the anticipated
transport.

This version requires the vocabulary but not full ActivityPub server behavior:
inbox and outbox HTTP delivery, WebFinger discovery and HTTP Signatures are not
conformance requirements here. A future version is expected to raise the floor to
full ActivityPub for all participants, at which point the vocabulary-only profile
may become a compatibility profile. An implementation built against this version
should expect to be re-evaluated against that one. This paragraph is the
specification's single statement of that roadmap; other sections cite it.

**ISO/IEC 29147 and 30111.** ISO 29147 specifies vulnerability disclosure
practices; ISO 30111 specifies vulnerability handling processes. Vultron
implements the multi-party coordination layer those standards describe at a
high level. The CERT Guide to Coordinated Vulnerability Disclosure provides
the practitioner-level complement.

!!! info "See also"
    - [ISO Crosswalks](../iso_crosswalks/index.md)
    - [CERT Guide to Coordinated Vulnerability Disclosure](https://certcc.github.io/CERT-Guide-to-CVD)

### 1.4 Document Conventions

This specification uses the key words defined in
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119): **MUST**, **MUST NOT**,
**REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**,
**RECOMMENDED**, **MAY**, and **OPTIONAL**.

Sections marked `[N]` are normative. Sections marked `[I]` are informative.
Sections marked `[N/I]` contain a mix; normative requirements are explicitly
flagged.

**State names.** This specification writes state names in full, in prose form:
*Received*, *Active*, *Signatory*, *Fix Ready*. Where the name of a specific
enumerated value matters — for example when citing an implementation's
enumeration — the value is written in code font with its machine as a prefix, as
in `RM.RECEIVED` or `PEC.SIGNATORY`. The two forms name the same state.

**Case-state notation.** The Case State axes use one letter per condition. A
lowercase letter means the condition is not met; an uppercase letter means it is.
`Vfd` therefore means the vendor is aware, the fix is not ready, and the fix is
not deployed. An arrow names the transition that flips one letter, so `f→F` is
the change from "fix not ready" to "fix ready". An asterisk is a wildcard: `pX*`
matches any state in which `p` is lowercase and `X` is uppercase.

---
