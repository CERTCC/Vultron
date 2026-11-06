!!! note "Four dimensions, five state machines"
    Case State (CS) is a compound of two independent axes, so the protocol realizes four tracked dimensions as **five** state machines:

    - **VFD** — Vendor Aware, Fix Ready, Fix Deployed. Participant-specific: it records what one participant has done ([§8.1 VFD — Vendor Aware, Fix Ready, Fix Deployed](../tracking-models.md#81-vfd-vendor-aware-fix-ready-fix-deployed)).
    - **PXA** — Public Aware, Exploit Public, Attacks Observed. Participant-agnostic: it records the state of the world, and it is shared case state ([§8.2 PXA — Public Aware, Exploit Public, Attacks Observed](../tracking-models.md#82-pxa-public-aware-exploit-public-attacks-observed)).

    This specification says "four dimensions" when describing what is tracked and "five state machines" when describing what the protocol defines.
    Both counts are correct; they count different things.

    The Vultron implementation splits VFD into two machines, so it has six.
    A vendor path, `CS_vf` (`vf`, `Vf`, `VF`), holds Vendor Aware and Fix Ready.
    A deployer path, `CS_d` (`d`, `D`), holds Fix Deployed.
    Together the two paths give the same four VFD states (`vfd`, `Vfd`, `VFd`, `VFD`) and the same 32 compound CS states.
