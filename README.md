# iso-diagram skill

## Overview

This skill creates isometric diagrams in 2 opinionated styles with text callouts and simplified detail.

### `iso-tree`

An isometric hierarchy diagram which displays a multi-layered set of entities which may have multiple children as the diagram moves downwards.


![Example iso-tree diagram of an AWS network, illustrating relationships and connectivity between an AWS region, VPC, subnets, and security groups, with a color-matched callout card for each level.](./iso-diagram/examples/aws-tree.png)

### `iso-stack`

Also called an "exploded" or "exploded isometric view", this type of diagram displays several layers as self-contained "slabs" whose child items may be connected by a through-connector.

![Example iso-stack diagram of a request traveling through an AWS Region, VPC, subnets, security groups, and finally individual resources. Color-matched text callouts provide a brief description of each major resource type.](./iso-diagram/examples/aws-stack.png)

The default output is `svg`, but it also supports `png`. The assumption is that the user or agent invoking the skill can utilize a separate tool to convert the `svg` output into other image formats.

## Style

This skill has a default set of fonts, icons, color palettes, and design principles which guide the creation of each diagram. You may provide customization options as part of the skill invocation to change these.

## Installation

Install this skill by copying the `iso-diagram` folder to your agent's `skills` directory. Nothing in the skill is agent-specific, so it should work with your agent of choice.

## License

License detail is in [LICENSE](./LICENSE). Note that this skill includes bundled fonts, and downloads Feather and Lucide icons on first use. Both have their own licenses which should be respected.

In short: Feel free to copy it, but keep it open, and please contribute your changes here. :)
