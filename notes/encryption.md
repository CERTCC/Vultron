# Encryption implementation notes

ActivityPub itself has been extended to automate many encrypted messaging
functions, including putting public keys into Actor profiles. The Vultron
implementation should leverage this existing work as much as possible.
CaseActors would ideally generate a public key pair at instantiation, and then
share the public key out to case participants who could choose to encrypt
messages sent back to the case. Actors in general should be able to decrypt
messages encrypted to their public key within the message routing and
dispatching process. Decryption probably belongs upstream of the dispatching
process, because dispatching to handlers depends on semantic recognition.
CaseActors sending messages to Actors that have encryption keys on their profile
should default to encrypting messages to the correct recipient's public key.
Mastodon already has public key distribution, see for example ><https://docs>.
joinmastodon.org/spec/activitypub/#publicKey> and <<https://docs.joinmastodon>.
org/spec/security/>

There is an open question regarding whether a single update can be encrypted to
multiple keys (also, can the To: address include all the actors at once), or
should the CaseActor do something like a
`for participant in case.participants: send_message_to(participant.actor, message)`
so that any given message is just between the recipient actor and the CaseActor.
This will have implications to how the encryption is implemented on outgoing
messages.