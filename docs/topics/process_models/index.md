# Vultron Process Models

The Vultron Protocol defines three main processes in terms of deterministic finite automata (DFAs):

```mermaid
---
title: Vultron Process Models
---
graph LR
    RM[[Report Management]]
    EM[[Embargo Management]]
    CS[[Case State]]
    RM --> EM
    RM --> CS
    EM --> RM
    EM --> CS
    CS --> EM
    CS --> RM
```

A CVD case is coordinated by multiple agents (Reporters, Vendors, Coordinators, etc.),
each running these processes in parallel and interacting with each other.

```mermaid
---
title: Vultron Agents Interacting
---
graph LR
    subgraph Agent2
        RM2[[Report Management]]
        EM2[[Embargo Management]]
        CS2[[Case State]]
    end
    subgraph Agent1
        RM1[[Report Management]]
        EM1[[Embargo Management]]
        CS1[[Case State]]
    end
    RM1 --> EM1
    RM1 --> CS1
    EM1 --> RM1
    EM1 --> CS1
    CS1 --> EM1
    CS1 --> RM1
    RM2 --> EM2
    RM2 --> CS2
    EM2 --> RM2
    EM2 --> CS2
    CS2 --> EM2
    CS2 --> RM2
    Agent1 --> Agent2
    Agent2 --> Agent1
```



## [Report Management process](rm/index.md)

{% include-markdown "./rm/index.md" start="<!-- start_excerpt -->" end="<!-- end_excerpt -->" %}

{% include-markdown "./rm/rm_state_machine_diagram.md" %}

[Read More...](rm/index.md)

## [Embargo Management process](em/index.md)

{% include-markdown "./em/index.md" start="<!-- start_excerpt -->" end="<!-- end_excerpt -->" %}

{% include-markdown "./em/em_dfa_diagram.md" %}

[Read More...](em/index.md)

## [Case State process](cs/index.md)

{% include-markdown "./cs/index.md" start="<!-- start_excerpt -->" end="<!-- end_excerpt -->" %}

{% include-markdown "./model_interactions/cs_global_local.md" %}

[Read More...](cs/index.md)