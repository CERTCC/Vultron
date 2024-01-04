# Vultron ActivityStreams Objects

Vultron ActivityStreams (Vultron AS) is an extension of the
[ActivityStreams vocabulary](https://www.w3.org/TR/activitystreams-vocabulary/)
to describe the mapping of Vultron to ActivityStreams.

## Actors

The following ActivityStreams actor types can be used in Vultron:

- `as:Person`
- `as:Organization`
- `as:Group`
- `as:Service`
- `as:Application`

## Other Objects

### Vultron-specific objects

We define the following objects for use in the Vultron AS vocabulary:

VulnerabilityReport
VulnerabilityCase
CaseStatus
CaseParticipant
ParticipantStatus
EmbargoEvent

### ActivityStreams native objects

ActivityStreams also includes a number of native object types, including:

- `as:Article`
- `as:Collection`
- `as:CollectionPage`, including `as:OrderedCollection` and `as:OrderedCollectionPage`
- `as:Document`, including `as:Audio`, `as:Image`, and `as:Video`
- `as:Event`
- `as:Note`
- `as:Page`
- `as:Place`
- `as:Profile`
- `as:Relationship`
- `as:Tombstone`

Of these, we mainly use `as:Note` to represent comments on a `VulnerabilityCase`.

!!! tip "Articles and Documents"

    Obviously a VulnerabilityReport or advisory draft could also be an 
    `as:Article` or `as:Document`, but at the moment we don't use those types 
    explicitly.
