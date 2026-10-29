## 16. References

### 16.1 Normative References

These documents are required to implement this specification.

| Reference | Title |
|---|---|
| [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) | Key words for use in RFCs to Indicate Requirement Levels |
| [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) | Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words |
| [ActivityStreams 2.0 Core](https://www.w3.org/TR/activitystreams-core/) | Activity Streams 2.0, World Wide Web Consortium (W3C) Recommendation |
| [ActivityStreams 2.0 Vocabulary](https://www.w3.org/TR/activitystreams-vocabulary/) | Activity Vocabulary, W3C Recommendation |
| [JSON-LD 1.1](https://www.w3.org/TR/json-ld11/) | JSON-LD 1.1: A JSON-based Serialization for Linked Data, W3C Recommendation |
| [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259) | The JavaScript Object Notation (JSON) Data Interchange Format |
| [FEP-8b32](https://codeberg.org/fediverse/fep/src/branch/main/fep/8b32/fep-8b32.md) | Object Integrity Proofs, Fediverse Enhancement Proposal. The form of the `proof` an activity carries ([§15.1 Trust Model](considerations.md#151-trust-model)) |
| [Data Integrity EdDSA Cryptosuites](https://www.w3.org/TR/vc-di-eddsa/) | Data Integrity EdDSA Cryptosuites v1.0, W3C Recommendation. Defines the `eddsa-jcs-2022` cryptosuite |
| [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785) | JSON Canonicalization Scheme (JCS). The canonical form that `eddsa-jcs-2022` signs |

### 16.2 Informative References

These documents provide context. They are not required to implement this
specification.

| Reference | Title |
|---|---|
| [ActivityPub](https://www.w3.org/TR/activitypub/) | ActivityPub, W3C Recommendation. The anticipated transport; not required by this version ([§1.3 Relationship to Existing Standards](introduction.md#13-relationship-to-existing-standards)) |
| [ISO/IEC 29147:2018](https://www.iso.org/standard/72311.html) | Information technology — Security techniques — Vulnerability disclosure |
| [ISO/IEC 30111:2019](https://www.iso.org/standard/69725.html) | Information technology — Security techniques — Vulnerability handling processes |
| [CERT Guide to CVD](https://certcc.github.io/CERT-Guide-to-CVD) | The CERT Guide to Coordinated Vulnerability Disclosure. Source of this specification's definition of *vulnerability* ([§2.1 Actors, Participants and Cases](introduction.md#21-actors-participants-and-cases)) |
| [CVE Program](https://www.cve.org/) | Common Vulnerabilities and Exposures (CVE) Numbering Authority operational rules, referenced at [§13.4.3 CVE ID Assignment](conformance.md#1343-cve-id-assignment) |
| [RFC 7033](https://www.rfc-editor.org/rfc/rfc7033) | WebFinger. The anticipated participant-discovery mechanism ([§5.3 Transport](layers.md#53-transport-ni)) |
| [RFC 9421](https://www.rfc-editor.org/rfc/rfc9421) | HTTP Message Signatures. Optional transport authentication for a production deployment, in addition to the `proof` in each activity ([§15.1 Trust Model](considerations.md#151-trust-model)) |

---
