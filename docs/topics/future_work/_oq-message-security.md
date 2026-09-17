!!! warning "Open question: what does a deployment have to sign and encrypt?"

    The prototype signs nothing and encrypts nothing.
    Activities travel as plaintext AS2 JSON over HTTP, and the adapter for signed remote delivery is a stub (OX-10-004).
    Treat the prototype as a demonstration of coordination logic rather than a deployable service.
    Concern [#509](https://github.com/CERTCC/Vultron/issues/509) tracks the gap.

    Encryption has a design.
    `specs/encryption.yaml` (ENC-01 through ENC-03) gives every actor a key pair, publishes the public key in the actor profile, and places decryption in the inbox handler ahead of semantic extraction, so handlers still receive typed and validated activities.
    Every requirement in that file carries `scope: production`.
    They state what a deployment owes, and the prototype is not a deployment.

    Signing has no specification yet.
    The intended shape is two signatures on a relayed activity: an inner one from the originating Participant and an outer one from the CASE_MANAGER that relayed it, so a recipient can verify origin and relay position independently.
    HTTP Message Signatures (RFC 9421) is the candidate transport mechanism ([#892](https://github.com/CERTCC/Vultron/issues/892), [#1163](https://github.com/CERTCC/Vultron/issues/1163)).

    Three things are open.
    Which of these requirements a deployment claiming Vultron conformance must satisfy is undecided.
    Whether per-recipient encryption (ENC-02-002) is sufficient for cases with many Participants, or whether a multi-recipient envelope format is warranted, has not been settled.
    And key material binds to an actor identity rather than to a case, so how many cases one CASE_MANAGER actor serves determines how much key separation a deployment gets.
    Work is tracked under epic [#1156](https://github.com/CERTCC/Vultron/issues/1156), with the actor identity model itself still pending ([#2841](https://github.com/CERTCC/Vultron/issues/2841)).
