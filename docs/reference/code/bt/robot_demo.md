# Robot Behavior Tree Demo

This is a demo of a behavior tree for a robot.
It has no practical use for Vultron, rather it's an introduction to how to use the behavior tree
framework we've built.

We're providing this as an example to show how to build a behavior tree that can be used
to implement some context-aware behavior.

## Behaviors

The robot has a number of behaviors:

- If the ball is in the bin, it will stop.
- If the ball is in the robot's grasp and it is near the bin, it will put it in the bin.
- If the ball is in the robot's grasp and it is not near the bin, it will move toward the bin.
- If the ball is nearby, it will try to pick it up (and sometimes fail)
- If the ball is not nearby, it will move toward the ball.
- If the ball is not found, it will search for it.
- If it fails to complete its task, it will ask for help.

## The Behavior Tree

The tree structure is shown below.

{% include-markdown './robot_demo_diagram.md' %}

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

!!! example Running the Demo
    ```shell
     # if vultron package is installed
    # run the demo
    $ vultrabot --robot
    
    # print the tree and exit
    $ vultrabot --robot --print-tree
    
    # if vultron package is not installed
    python -m vultron.bt.base.demo.robot
    ```

When the tree is run, it will look something like this:

```text
{% include-markdown './robot_tree_example.txt' %}
```

## Demo Code

::: vultron.bt.base.demo.robot
    options:
        heading_level: 3
