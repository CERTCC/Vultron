## 15. IANA and Namespace Considerations [I]

**Vultron vocabulary namespace.** The Vultron ActivityStreams 2.0 (AS2) vocabulary namespace is
`https://certcc.github.io/Vultron/ns`. This is the initial, provisional Uniform Resource Identifier (URI),
hosted on GitHub Pages. A permanent URI registration (for example, via a
`w3id.org` redirect) is planned for a future version of this specification.
See ADR-0069.

**JSON-LD context document.** The normative JavaScript Object Notation for Linked Data (JSON-LD) context is identified by
`https://certcc.github.io/Vultron/ns/context.jsonld`.
Every outbound Vultron message names this URI as its `@context` value ([§5.2 Serialization](layers.md#52-serialization)):

```python exec="true" idprefix=""
from vultron.metadata.specs.docs_render import requirement_callout; print(requirement_callout("VM-10-001"))
```

That URI does not currently dereference.
The context document is withheld from publication until it is served at the wire-versioned path that ADR-0106 defines.
At this version the namespace is therefore a stable identifier, not a retrievable document.
An implementation therefore cites the URI as an identifier, and processes a message without fetching it.

**AS2 extension type naming conventions.** Vultron type names follow PascalCase
without an `as_` prefix in wire output (for example, `"type": "VulnerabilityCase"`
rather than `"type": "as:VulnerabilityCase"`). The Vultron JSON-LD context
declares all type names, so implementations citing only the Vultron context URI
do not need to separately declare the AS2 namespace.

**IANA registration.** No new IANA registrations are required by the current
version of this specification. If the Vultron namespace moves to a
standards-track document, an IANA media type registration for the Vultron
JSON-LD profile may be appropriate at that time.

---
