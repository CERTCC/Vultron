# Vultrabot Behavior Tree Demo

This demo implements a far more complex behavior tree than the simple
ones in the [Pacman](./pacman_demo.md) and [Robot](./robot_demo.md) demos.

The Behavior Tree for this demo is essentially the entire tree defined in the
[Behavior Logic](../topics/behavior_logic/cvd_bt.md) section.

## Demo Output

!!! example "Usage"

    ```shell
    # if vultron package is installed
    # run the demo
    $ vultrabot
    # or
    $ vultrabot --cvd
    
    # print the tree and exit
    $ vultrabot --cvd --print-tree
    
    # if vultron package is not installed
    $ python -m vultron.bt.base.demo.vultrabot
    ```

When the tree is run, it will look something like this:
```text
{% include-markdown './vultrabot_tree_example.txt' %}
```

The full tree is too large to display here, but you can run the demo to see it.

## Demo Code

::: vultron.demo.vultrabot
    options:
        heading_level: 3
