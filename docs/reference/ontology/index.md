# Ontology

The Vultron repository carries a set of [Web Ontology Language (OWL)](https://www.w3.org/TR/owl2-overview/){:target="_blank"} files under `ontology/`.
They were written while translating the formal Vultron protocol message types onto the ActivityStreams 2.0 (AS2) vocabulary, so they are an artifact of that translation rather than a component of the protocol.
They are unmaintained, no part of the prototype reads them, and no published Vultron artifact depends on them.
This page records that disposition: the files stay in the repository at `ontology/`, and they are not published on this site.

{% include-markdown "../../includes/not_normative.md" %}

## The files

| File | Subject |
|---|---|
| `vultron_activitystreams.ttl` | Vultron message types as an extension of the AS2 vocabulary |
| `vultron_protocol.ttl` | Vultron protocol concepts |
| `vultron_process.ttl` | The individual Vultron process models |
| `deterministicfiniteautomata.ttl` | A generic deterministic finite automaton (DFA) vocabulary the process models build on |
| `rfc2119.ttl` | The requirement keywords of RFC 2119 |

The last two model generic concepts rather than Vultron ones.
The directory also holds the W3C ActivityStreams vocabulary that the Vultron files import, `vulspolicy.ttl` — an unnamed draft that nothing imports — and the catalog and properties files the Protégé editor writes.

## Declared namespaces

The Vultron files declare namespaces under `http://www.cert.org/ns/`, such as `http://www.cert.org/ns/vultron_protocol#`.
That prefix does not resolve.
It also differs from the namespace the JavaScript Object Notation for Linked Data (JSON-LD) vocabulary declares, `https://certcc.github.io/Vultron/ns#`.
The two declarations are unreconciled.

## What carries the mapping

[Message Types](../messages/index.md) is the maintained mapping between the formal message set and the AS2 wire vocabulary.
[ADR-0083](../../adr/0083-formal-message-set-and-as2-vocabulary-are-different-shapes.md) records why the two vocabularies are deliberately different shapes.
