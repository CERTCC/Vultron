---
status: accepted
date: 2023-10-23
deciders: adh
---
# Model Processes with Behavior Trees

## Context and Problem Statement

The Vultron protocol is defined as a set of three interacting state machines for each agent:

- Report Management
- Embargo Management
- Case State Management

We have a need to simulate the behavior of these state machines in order to test the protocol.
However, the interactions between them can be complex, so we need a way to model those interactions.

## Decision Drivers

- Need to simulate complex interactions between state machines
- Need to explore and exercise state space of the protocol even if some states are rarely reached in practice

## Considered Options

- Object-oriented Agent implementation
- Behavior Tree Agent implementation

## Decision Outcome

Chosen option: "Behavior Tree Agent implementation", because behavior trees allow us to model complex interactions
between state machines. By building in stochastic behaviors, they also allow us to explore and exercise the state space
of the protocol even if some states are rarely reached in practice. 

### Consequences

- Behavior trees are a new technology for the team, so there will be a learning curve.
- Simulating changes to process logic should be easier with behavior trees than with object-oriented code.


## Pros and Cons of the Options

### Object-oriented implementation

Good, because:
- Standard OO python approach understood by the team
- State management could be implemented as a set of classes for each state machine

Bad, because:
- Complex interactions between state machines would be difficult to model and maintain
- Reactive behaviors (e.g., based on state changes in outside world) would be difficult to model

## More Information

- Michele Colledanchise, Petter Ögren: Behavior Trees in Robotics and AI
  - [book @ Amazon](https://www.amazon.com/Behavior-Trees-Robotics-Introduction-Intelligence/dp/1138593737)
  - [pdf @ arXiv](https://arxiv.org/abs/1709.00084)
- Petter Ögren's YouTube channel has a number of good videos on Behavior Trees
  - https://www.youtube.com/@petterogren7535
- Wikipedia
  - [Behavior Tree (artificial intelligence, robotics and control)](https://en.wikipedia.org/wiki/Behavior_tree_(artificial_intelligence,_robotics_and_control))