```mermaid
---
title: Simplified pxa State Diagram
---
stateDiagram-v2
    direction LR
    [*] --> pxa
    
    pxa --> Pxa : P
    pxa --> PXa : X,P
    pxa --> pxA : A
    
   
    pxA --> PxA : P
    pxA --> PXA : X,P

    Pxa --> PxA : A
    Pxa --> PXa : X
    
    PXa --> PXA : A
    PxA --> PXA : X
    PXA --> [*]
```
