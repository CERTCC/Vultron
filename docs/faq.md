# Vultron Protocol Frequently Asked Questions

## What do we need to move the Vultron Protocol to widespread use?

First, we need to finish the protocol and get it to a sufficiently stable state that we can start to use it even in 
test environments.  We're not there yet.

In the meantime, there are a number of other things that can help. We're looking for help with:


## How do we apply encryption to ActivityPub messages to enable end-to-end encryption?

We're of the opinion that encrypted messaging is a feature that should be available to all users of
ActivityPub, not just those using the Vultron Protocol to coordinate vulnerability cases.
Therefore, our position is that end-to-end encryption would be better implemented as a layer on top of the ActivityPub
protocol, rather
than as a specific feature of the Vultron Protocol.
From what we can tell, the topic has come up before in the ActivityPub community, but there is no
standardized solution yet.
We're currently focused on developing the Vultron Protocol, but we realize that encryption may be a requirement for
widespread adoption, so we're keeping an eye on the topic.

Some relevant links include:

- A November 2022 blog
  post [Towards End-to-End Encryption for Direct Messages in the Fediverse](https://soatok.blog/2022/11/22/towards-end-to-end-encryption-for-direct-messages-in-the-fediverse/)
- [Issue #225](https://github.com/w3c/activitypub/issues/225) on the W3C ActivityPub Github repo talks about the
  need for encrypted content, but it seems to have been closed without a solution in 2017.
    - However, a much more
      recent [April 2023 comment](https://github.com/w3c/activitypub/issues/225#issuecomment-1493887382)
      mentions:
      > If we restrict to direct message (with a single recipient) one may just encrypt the message (Note) payload using
      the
      public key of the recipient. So, if the recipient holds her own private key, she can decrypt the message payload.
      The
      main obstacle I see is the common practice to use HTTP signature, so that private kays must resides on server and
      not
      on clients.
- There have been numerous [Discussions](https://socialhub.activitypub.rocks/search?q=end+to+end+encryption) on the
  [ActivityPub SocialHub](https://socialhub.activitypub.rocks/) that mention end-to-end encryption.

We are interested in any developments in this space, please let us know if you are aware of more recent developments.
We'd be interested to know how we could help with efforts to bring encrypted messaging to ActivityPub.

## What are the requirements for contributing?

See [CONTRIBUTING](about/contributing.md)

