!!! note "Four dimensions, five state machines"
    Case State (CS) is a compound of two independent axes, so four tracked
    dimensions are realized as **five** state machines:

    - **VFD** — Vendor Aware, Fix Ready, Fix Deployed. Participant-specific: it
      records what one participant has done
      ([§8.1](../index.md#81-vfd-vendor-aware-fix-ready-fix-deployed)).
    - **PXA** — Public Aware, Exploit Public, Attacks Observed.
      Participant-agnostic: it records the state of the world, and it is shared
      case state
      ([§8.2](../index.md#82-pxa-public-aware-exploit-public-attacks-observed)).

    This specification says "four dimensions" when describing what is tracked and
    "five state machines" when describing what an implementation must provide.
    Both counts are correct; they count different things.
