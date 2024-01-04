# Transferring Case Ownership

This was not part of the original Vultron protocol, but it seems like a
reasonable extension that could be useful in some cases, such as transferring a
case

- from a researcher to a vendor
- from a vendor to an upstream vendor
- from a vendor to a coordinator
- from a coordinator to a vendor
- between coordinators

```mermaid
flowchart LR
    subgraph as:Invite
        OfferCaseOwnershipTransfer
    end
    subgraph as:Accept
        AcceptCaseOwnershipTransfer
    end
    subgraph as:Reject
        RejectCaseOwnershipTransfer
    end
    subgraph as:Update
        UpdateCase
    end
    OfferCaseOwnershipTransfer --> AcceptCaseOwnershipTransfer
    OfferCaseOwnershipTransfer --> RejectCaseOwnershipTransfer
    AcceptCaseOwnershipTransfer --> UpdateCase
```
