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

# the spec

to begin, we need a specification of what things to create in the
system. we could define this in an inventory file, with a
backend-agnostic schema (see the [docs]() on how to do
this). alternatively, we could use the `alembic-file-generator` which
is included in the alembic repo. this gives us the ability to define
exactly how many objects our inventory should include:

```bash
$ cargo run --bin alembic-file-generator -- --kind inventory
```

this will generate an inventory file called `inventory.yaml`, check it
out before we move on!

# trying out a backend (netbox)

so, let's say that we want to start by trying out
[netbox](https://netboxlabs.com/docs/netbox/). this is a good first
target, since it requires no extra work to set up. the
inventory file from above is immediately applicable to netbox, we just
need to make a plan and apply it like so:

```bash
$ alembic plan --backend netbox --file inventory.yaml --output plan.json
```

```bash
$ alembic apply --backend netbox --plan plan.json
```

inspecting our local netbox inventory through the web interface we can
see that things are in order, e.g:

![fig. 1: netbox cables](./assets/netbox_cables.png)

# slightly trickier

if you didn't generate the inventory using the
`alembic-file-generator` you might have the data in a slightly
incorrect format. for example, maybe you're using something like
`/examples/walkthroughs/eval-fabric.yaml` in this repo. this file contains a
backend-agnostic spec for a very small system.

in this case, there's a small discrepancy in how netbox handles ip
adresses compared to how they are stored in the schema. the interface
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
alembic map --file ./examples/walkthroughs/eval-fabric.yaml --spec ./examples/walkthroughs/eval-fabric-netbox.yaml -o inventory.json
```

this new file can be planned and applied just like the file generated
by alembic-file-generator above!

# other backends (nautobot)
