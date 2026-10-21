---
title: "shopping for backends"
date: 2026-09-04
slug: shopping-for-backends
tags: [alembic, network automation, tooling]
summary: "in which we help out the imaginary person in charge of choosing a new dcim system"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/alembic
    - label: docs
      url: https://github.com/cyberwitchery/alembic/tree/main/docs
    - label: netbox
      url: https://netboxlabs.com/docs/netbox/
    - label: nautobot
      url: https://github.com/nautobot/nautobot
author: Erik Svedäng
---

picture this; you're the person in charge of picking a suitable dcim
system to keep track of you business' inventory. to get a good feel
for the new system, you want it filled up with a lot of *stuff*,
preferably with realistic configurations. instead of adding each
such thing manually via a web interface, wouldn't it be much nicer if
a tool did it for you? and ideally this tool would be driven by
backend-agnostic spec that could be reused for each potential system
that you want to try out? and what if someone had already created such
a spec, so you could just use it and modify it as you like?!

well, we got some good news for you; alembic can do just this (and
more). this blog post will show you how.

# the inventory

to begin, you need a specification of what things to create in the
system, stored in an inventory file. there are many options for how to
obtain such a file:

1. you could define it yourself, using a backend-agnostic schema. see
[ir
docs](https://github.com/cyberwitchery/alembic/blob/main/docs/ir.md)
on how to do this. this will teach you the most about how the file
format and alembic ir works. if you are ever tempted to use a coding agent
for writing the file, there's a `SKILL.md` in the `alembic-cli` crate
that will help it out.

2. if you already have a system running with your own data,
[importing](https://github.com/cyberwitchery/alembic/blob/main/docs/cli.md#import)
that could make more sense. a benefit with this approach is that you
would immediately see if there's something that the new backend can't
represent in a good way.

3. you could just take one of the example files from the `alembic`
repo, e.g
[/examples/inventory.yaml](https://github.com/cyberwitchery/alembic/blob/main/examples/inventory.yaml). this
is definitely the quickest way! those files are quite small though, and
not particularly representative of what a messy real world system
would look like.

4. for flexibility and stress testing, you could use the
`alembic-file-generator` which is included in the alembic repo
(install it with `cargo install --path ./crates/alembic-file-generator`). this
gives you the ability to define exactly how many objects our inventory
should include:

```bash
$ alembic-file-generator --kind=inventory --num-devices=10000
```

before we move on, make sure that you have some kind of inventory file
(named `inventory.yaml`) at hand!

# trying out a backend (netbox)

let's say that we want to start by trying out
[netbox](https://netboxlabs.com/docs/netbox/). this is an especially
good first target if you used the file generator or
`examples/inventory.yaml`, since it requires no extra work to set up
then. just make a plan and apply it like so:

```bash
$ alembic plan --backend netbox --file inventory.yaml --output plan.json
```

the cli tool will display a list of all the planned changes. if it
looks good, apply those changes:

```bash
$ alembic apply --backend netbox --plan plan.json
```

inspecting our local netbox inventory through the web interface we can
see that things are in order, e.g:

![fig. 1: netbox devices](./assets/netbox_devices.jpg)

# massaging the data

depending on how you your `inventory.yaml` file was constructed, it
might have its data in a slightly incompatible format. this is no
reason for panic, and something that alembic will handle with no trouble!

for example, if you're using `/examples/walkthroughs/eval-fabric.yaml`
from the alembic repo, there's a small discrepancy in how netbox handles ip
adresses compared to how they are stored in that schema. the interface
assigned to an ip is stored under the key `assigned_object` rather
than `assigned_interface`. to solve this, we can use `alembic
map` which transforms data. here's the relevant snippet from
`/examples/walkthroughs/eval-fabric-netbox.yaml`

```
rules:
  - name: rename-assignment
    match: ipam.ip_address
    emit:
      type: ipam.ip_address
      key: {address: "${key.address}"}
      attrs:
        address: "${attrs.address}"
        assigned_object: "${attrs.assigned_interface}"
  - name: rest
    match: "*"
    emit: passthrough
```

in short, this transforms all objects of type `ipam.ip_address` and
leaves anything else as-is.

we can use this to generate a new file with ir that has the correct
keys for netbox:

```bash
alembic map --file ./examples/walkthroughs/eval-fabric.yaml --spec ./examples/walkthroughs/eval-fabric-netbox.yaml --output inventory.yaml
```

the new file can be planned and applied just like the `inventory.yaml`
file generated by alembic-file-generator above!

# other backends (nautobot)
