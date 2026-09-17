!!! warning "Open question: what does a deployment sign and encrypt?"

    The prototype does not sign or encrypt its messages.
    Activities move as plaintext AS2 JSON on HTTP.
    The adapter for signed remote delivery is a stub (OX-10-004).
    The prototype is a demonstration of coordination logic, not a service for deployment.
    Concern [#509](https://github.com/CERTCC/Vultron/issues/509) records this gap.

    Encryption has a design.
    `specs/encryption.yaml` (ENC-01 through ENC-03) gives each actor a key pair.
    It publishes the public key in the actor profile.
    It also puts decryption in the inbox handler, before semantic extraction.
    Each handler thus continues to receive typed and validated activities.

    Each requirement in that file has `scope: production`.
    The requirements apply to a deployment, and the prototype is not a deployment.

    Signing has no specification.
    The intended shape puts two signatures on a relayed activity.
    The inner signature comes from the Participant that originated the activity.
    The outer signature comes from the CASE_MANAGER that relayed it.
    A recipient can thus verify the source and the relay position independently.
    HTTP Message Signatures (RFC 9421) is the candidate transport mechanism ([#892](https://github.com/CERTCC/Vultron/issues/892), [#1163](https://github.com/CERTCC/Vultron/issues/1163)).

    Three points are open.
    First, the project has not selected the requirements that apply to a deployment that claims Vultron conformance.
    Second, per-recipient encryption (ENC-02-002) can be sufficient for a case that has many Participants, or a multi-recipient envelope format can be necessary.
    Third, key material applies to an actor identity, not to a case.
    The quantity of cases that one CASE_MANAGER actor holds thus sets the separation between the keys of those cases.
    Epic [#1156](https://github.com/CERTCC/Vultron/issues/1156) records this work, and the actor identity model is open ([#2841](https://github.com/CERTCC/Vultron/issues/2841)).
