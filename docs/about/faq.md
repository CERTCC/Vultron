---
description: >
  Short answers to the questions people ask first about Vultron, each pointing
  to the page that answers it in full.
stakeholder_type: ALL
level: 100
---

# Vultron Protocol Frequently Asked Questions

Each answer here is a summary and a pointer.
The page it points to is the authority.

## What kind of thing is Vultron?

Vultron is a protocol, like the Simple Mail Transfer Protocol (SMTP), and not a platform, like a messaging service.
It defines the messages that organizations exchange while coordinating the disclosure of a vulnerability, so that each organization can keep using its own tracker and still work a case with its partners.
See [What Is Vultron?](../topics/background/what-is-vultron.md).

## Is Vultron software I can install?

The protocol is a specification: the [Vultron Protocol Specification](../reference/vultron-spec/index.md) is the normative document, and any system can implement it.
This site also documents a reference implementation, written in Python, that exists to demonstrate and test the specification.
You can run it as a test peer for your own system, or start from it and replace the components your organization already has; the [tutorials](../tutorials/index.md) show how.
Vultron itself is not a product: it is a feature set that products implement.

## Would it help my organization?

It helps when you coordinate vulnerability cases with organizations that do not share your systems.
Today that means holding an account on each partner's coordination platform, or falling back to email and hand-updated tickets.
With Vultron, your own tracker sends and receives the case traffic.
Pick the page written for your situation:

- [You handle vulnerability reports and coordinate cases with other organizations](../start/coordinate-cases.md)
- [You maintain a vulnerability tracker and want it to talk to your partners](../start/connect-your-tracker.md)
- [You study how vulnerability disclosure works and want the models behind it](../start/study-the-process.md)

## Vultron does not validate reports, prioritize them, or draft advisories. Why would I want it?

Because those are the decisions your organization already makes, and the protocol is what carries their results to your partners.
Each of them is a declared **call-out point**: a place where the protocol stops and your own tool, service, or analyst answers.
SMTP does not write your mail either.
See [What Vultron is not](../topics/background/what-is-vultron.md#what-vultron-is-not) for the list of things it is not, each paired with where your system plugs in, and the [Capability Model](../topics/capability_model/index.md) for how the call-out points are organized.

## How does Vultron relate to the standards we already follow?

The protocol is designed to be used alongside [ISO/IEC 29147](../reference/iso_crosswalks/iso_29147_2018.md) (vulnerability disclosure), [ISO/IEC 30111](../reference/iso_crosswalks/iso_30111_2019.md) (vulnerability handling processes), and [ISO/IEC TR 5895](../reference/iso_crosswalks/iso_5895_2022.md) (multi-party coordinated vulnerability disclosure).
The [ISO crosswalks](../reference/iso_crosswalks/index.md) map each standard's clauses onto the protocol, and the [SSVC crosswalk](../reference/ssvc_crosswalk.md) does the same for Stakeholder-Specific Vulnerability Categorization (SSVC).

## Which messages does the protocol define?

Twenty-eight formal message types, grouped by the state machine they belong to: Report Management, Embargo Management, Case State, and general messages.
On the wire they are ActivityStreams 2.0 activities delivered over ActivityPub.
See [Message Types](../reference/formal_protocol/messages.md) for the formal set and [Message Types](../reference/messages/index.md) in the reference section for the wire mapping.

## Is the protocol finished?

The specification is published and versioned, and the reference implementation tracks it.
Both continue to change: [What's New](whats_new.md) lists the pages added recently, and the [decision records](../adr/index.md) record what changed and why.
[§12 Conformance in the specification](../reference/vultron-spec/conformance.md#12-conformance-n) defines what a system claims when it says it conforms, so a claim can be checked against a stated version of the specification.

## Can Vultron messages be end-to-end encrypted?

Not by anything the protocol adds.
Vultron messages are ActivityPub messages, and our position is that end-to-end encryption belongs in ActivityPub itself, where every user of the protocol would benefit, rather than in a feature specific to Vultron.
The ActivityPub community has discussed it without settling on a standard; the trail runs from a [2017 W3C issue](https://github.com/w3c/activitypub/issues/225){:target="_blank"} through a [2022 design post](https://soatok.blog/2022/11/22/towards-end-to-end-encryption-for-direct-messages-in-the-fediverse/){:target="_blank"} to ongoing [SocialHub discussions](https://socialhub.activitypub.rocks/search?q=end+to+end+encryption){:target="_blank"}.
Transport security between actors' servers is a separate matter, and ActivityPub deployments already provide it over HTTPS.
If you know of progress on end-to-end encryption for ActivityPub, we would like to hear about it.

## How do I contribute?

See [Contributing](contributing.md).
