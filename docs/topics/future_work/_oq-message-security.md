!!! warning "Open question: what does a deployment sign and encrypt?"

    The prototype does not sign or encrypt its messages.
    Activities move as plaintext AS2 JSON on HTTP.
    The adapter for signed remote delivery is a stub (OX-10).
    The prototype is a demonstration of coordination logic, not a service for deployment.
    Concern [#509](https://github.com/CERTCC/Vultron/issues/509) records this gap.

    Encryption has a design.
    `specs/encryption.yaml` (ENC-01 through ENC-03) gives each actor a key pair.
    It publishes the public key in the actor profile.
    It also puts decryption in the inbox handler, before semantic extraction.
    Each handler thus continues to receive typed and validated activities.

    Each requirement in that file has `scope: production`.
    The requirements apply to a deployment, and the prototype is not a deployment.

    Signing has a design, but the prototype does not implement it yet.
    `specs/signing.yaml` (SIG-01 through SIG-05) puts a proof inside each activity that an actor sends ([ADR-0164](../../adr/0164-actors-sign-content-with-object-level-proofs-from-seeded-keys.md)).
    The proof uses the FEP-8b32 `eddsa-jcs-2022` form.
    It thus stays in the activity when the CASE_MANAGER relays the activity or records it in the case ledger.

    A relayed activity carries two proofs.
    The inner proof comes from the Participant that originated the activity.
    The outer proof comes from the CASE_MANAGER that relayed it.
    A recipient can thus verify the source and the relay position independently.

    A receiver gets each key from the actor profile of the author, and it refuses an activity without a valid proof.
    The prototype calculates each key pair from a fixed seed, so its keys make no security claim.
    HTTP Message Signatures, which Request for Comments (RFC) 9421 defines, are work for a production deployment ([#1184](https://github.com/CERTCC/Vultron/issues/1184)).

    Three points are open.
    First, the project has not selected the requirements that apply to a deployment that claims Vultron conformance.
    Second, per-recipient encryption (ENC-02-002) can be sufficient for a case that has many Participants, or a multi-recipient envelope format can be necessary.
    Third, key material applies to an actor identity, not to a case.
    The quantity of cases that one CASE_MANAGER actor holds thus sets the separation between the keys of those cases.
    Epic [#1156](https://github.com/CERTCC/Vultron/issues/1156) records this work, and the actor identity model is open ([#2841](https://github.com/CERTCC/Vultron/issues/2841)).
