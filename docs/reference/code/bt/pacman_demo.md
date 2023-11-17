# Pacman Bot Behavior Tree Demo

This is a demo of a behavior tree for a game playing bot.
It has no practical use for Vultron, rather it's an introduction to how to use the behavior tree
framework we've built.

We're providing this as an example to show how to build a behavior tree that can be used
to implement some context-aware behavior.

It implements a simplified Pacman game with a bot that eats pills and avoids ghosts.

## Behaviors

If no ghosts are nearby, Pacman eats one pill per tick.
But if a ghost is nearby, Pacman will chase it if it is scared, otherwise he will avoid it.
If he successfully avoids a ghost, he will eat a pill.
The game ends when Pacman has eaten all the pills or has been eaten by a ghost.

## Scoring

Scoring is as follows:

- 10 points per pill
- 200 points for the first ghost, 400 for the second, 800 for the third, 1600 for the fourth

There are 240 pills on the board. The max score is

$$(240 \times 10) + (200 + 400 + 800 + 1600) = 5400$$

## Differences from the real thing

If the game exceeds 1000 ticks, Pacman gets bored and quits (but statistically that should never happen).

We did not model power pellets, fruit, or the maze. Ghosts just randomly get scared and then randomly
stop being scared. Ghosts and pills are just counters. Ghost location is just a random "nearby" check.

## The Behavior Tree

The tree structure is shown below.

{% include-markdown './pacman_tree_diagram.md' %}

Legend:

| Symbol   | Meaning |
|----------| ------- |
| ?        | FallbackNode |
| &rarr;   | SequenceNode |
| &#8645;  | Invert |
| &#9648;  | ActionNode |
| &#11052;  | ConditionNode |
| &#127922; | Fuzzer node (randomly succeeds or fails some percentage of the time) |

## Demo Output

!!! example 
    
    ```shell
    # if vultron package is installed
    # run the demo
    $ vultrabot --pacman

    # print tree and exit
    $ vultrabot --pacman --print-tree

    # if vultron package is not installed
    $ python -m vultron.bt.base.demo.pacman
    ```

When the tree is run, it will look something like this:

```text
{% include-markdown './pacman_tree_example.txt' %}
```

## Demo Code

::: vultron.bt.base.demo.pacman
    options:
        heading_level: 3
