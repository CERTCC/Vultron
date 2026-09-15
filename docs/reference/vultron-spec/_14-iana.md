## 14. IANA / Namespace Considerations [I]

**Vultron vocabulary namespace.** The Vultron AS2 vocabulary namespace is
`https://certcc.github.io/Vultron/ns`. This is the initial, provisional URI,
hosted on GitHub Pages. A permanent URI registration (for example, via a
`w3id.org` redirect) is planned for a future version of this specification.
See ADR-0069.

**JSON-LD context document.** The normative JSON-LD context is at
`https://certcc.github.io/Vultron/ns/context.jsonld`. Implementations MUST
use this URI as the `@context` value for all outbound Vultron messages (§5.5).

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
