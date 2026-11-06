## 15. IANA and Namespace Considerations [N/I]

**Vultron vocabulary namespace.** The Vultron ActivityStreams 2.0 (AS2) vocabulary namespace is
`https://certcc.github.io/Vultron/ns`. This is the initial, provisional Uniform Resource Identifier (URI),
hosted on GitHub Pages. A permanent URI registration (for example, via a
`w3id.org` redirect) is planned for a future version of this specification.
See ADR-0069.

**JSON-LD context document.** The normative JavaScript Object Notation for Linked Data (JSON-LD) context is identified by
`https://certcc.github.io/Vultron/ns/context.jsonld`.
Every outbound Vultron message lists this URI in its `@context`, after the AS2 namespace ([§5.2 Serialization](layers.md#52-serialization)):

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("VM-10-001"))
```

That URI does not currently dereference.
The context document is withheld from publication until it is served at the wire-versioned path that ADR-0106 defines.
At this version the namespace is therefore a stable identifier, not a retrievable document.
A receiver processes a message without fetching it:

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("VM-10-003"))
```

**AS2 extension type naming conventions.** Vultron type names follow PascalCase
without an `as_` prefix in wire output (for example, `"type": "VulnerabilityCase"`
rather than `"type": "as:VulnerabilityCase"`). The Vultron JSON-LD context
declares all type names.
A message still lists the AS2 namespace before the Vultron context URI in its `@context`, because a receiver need not fetch the Vultron context to learn that it imports AS2 ([§5.2 Serialization](layers.md#52-serialization)).

**IANA registration.** No new IANA registrations are required by the current
version of this specification. If the Vultron namespace moves to a
standards-track document, an IANA media type registration for the Vultron
JSON-LD profile may be appropriate at that time.

---
