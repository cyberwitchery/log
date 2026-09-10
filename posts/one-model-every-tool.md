---
title: "one model, every tool: a fabric in nine shapes"
date: 2026-09-10
author: "Veit Heller"
slug: one-model-every-tool
tags: [alembic, network automation, tooling]
summary: "a fabric shows up as an ansible inventory, a nornir directory, a prometheus target list, an ssh config, a dns zone, a containerlab topology, two diagrams and an avd project. we emit all nine from a single data model model.<br/>`cargo install alembic-cli`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/alembic
    - label: docs
      url: https://github.com/cyberwitchery/alembic/tree/main/docs
    - label: crates.io
      url: https://crates.io/crates/alembic-cli
---

**disclaimer:** this heavily features alembic ops, the commercial layer on top
of alembic. the general idea applies to oss, but most of the connectors here are
only available with a commercial license.

a fabric is encoded in a lot of different files. if you run a full deployment of
alembic ops today, you end up with an ansible inventory, a nornir `hosts.yaml`,
a prometheus target list, an ssh config, a dns zone, a containerlab topology, and
potentially two different diagrams for the wiki. each is the same input
translated to a different tool’s vocabulary, and each is otherwise maintained by
hand, which means each drifts on its own accord.

this post takes a small fabric out of netbox and emits nine files from it. the
fabric is a clos: one site (`fra1`), two spines, two leaves, a full leaf-spine
mesh, a pair of peer links between the leaves, one management address per device.
small enough for us to read fully, big enough that hard stuff like grouping, cabling
and per-role variables all feature.

it also, incidentally, is what we use as a golden test in our ci.

the flow is a full alembic loop:

```
seed (apply) -> netbox -> import -> map (resolve) -> emit
```

let’s get to work!

## import

the seed is our desired state fed into netbox, applied the usual way, to make
sure that what we read are real netbox entities rather than a fixture (we don’t
trust those). import then pulls out the fabric, verified against a declared
schema.

```bash
alembic import -f import.yaml --backend-config backends/netbox.yaml -o imported.json
```

the result is observed ir: devices with a role, site, platform and
`primary_ip4` as *references*, plus the interfaces, the cables and the
addresses. the import runs with no state behind it (`import --stateless` makes
sure of that), so every uid is taken from the key rather than the seed state.
that’s what makes the output deterministic and diffable.

## map

the adapters want literals. an address, a platform slug, a name. so `map`
follows the references to get at the values.

```yaml
- name: devices
  match: "dcim.device"
  lookups:
    role:     { ref: "${attrs.role}",        get: "key.slug" }
    platform: { ref: "${attrs.platform}",    get: "key.slug" }
    ip:       { ref: "${attrs.primary_ip4}", get: "attrs.address" }
  emit:
    type: dcim.device
    key: { name: "${key.name}" }
    attrs:
      role: "${lookup.role}"
      role_group: "${attrs.role}"# kept as a ref
      kind: "${lookup.platform|clab_kind}"
      primary_ip: "${lookup.ip|cidr_host}" # 198.51.100.101/24 -> 198.51.100.101
      ansible_network_os: "${lookup.platform|ansible_os}"
      bgp_as: "${attrs.name|avd_bgp_as}"
```

`clab_kind`, `cidr_host`, `ansible_os` and `avd_bgp_as` are starlark
transforms we maintain in a separate file. cables pass through unchanged.
interfaces get renamed, `eth1` becomes `Ethernet1`, because avd validates
uplink names against the eos convention[^1]. one resolved model then feeds both
the flat inventories (which read the device) and the topology emitters (which
also read wiring).

a brief note about `role_group`. flat inventories need groups, and the obvious
place to put grouping is adapter config: a `group_by` key per backend, each with
its own variables. we used to do it like that.

now grouping is mapped ir. each device role becomes an `infra.group` object
whose key is the group name and whose attributes are the group vars, and the
device carries a reference to it. the topology emitters keep clustering off the
scalar `role`. neither emitter is configured with anything about the other. it
just works.

a single rule can fan out, which means the site can become two groups at once:
the fabric root the role groups nest under, and the reserved `all` group carrying
the fabric-wide defaults.

```yaml
- name: site-groups
  match: "dcim.site"
  emit:
    - type: infra.group
      key: { name: "${key.slug}" }
      uid: { v5: { type: infra.group, stable: "fabric=${key.slug}" } }
    - type: infra.group
      key: { name: all }
      uid: target
      attrs: { username: admin, ansible_user: admin }
```

since [0.9.0](/log/alembic-dev-log-2026-08) a rule that emits several objects
has to name each one’s identity. the fabric group pins a uid that the role groups
can name as their parent. `all` takes its identity from the rendered target,
and every site fans in to it.

is this delicate? yes. but what it’s got over a bespoke stack is that we can
focus on the data and its transformation rules instead of several ad-hoc scripts
in python that each need a pass when a bit of the schema changes.

## emit

every emitter is an [external adapter](/log/writing-an-external-adapter)
reading the same `resolved.json` through the normal plan/apply flow. alembic
ops thus is simply a collection of connectors that run the whole stack, and not
special trickery from the lab.

```bash
for name in containerlab dot mermaid ansible nornir avd ssh dns prometheus; do
  alembic plan  -f resolved.json --backend-config "backends/$name.yaml" -o "plan.$name.json"
  alembic apply -p "plan.$name.json" --backend-config "backends/$name.yaml"
done
```

the topology emitters read the cabling. the two diagram emitters were [the
subject of the last post](/log/diagrams-from-your-data-model). they cluster per
role and label each edge with the interface pair, so the six cables come out as
six edges (and we didn’t even have to transform anything about them!).

the flat emitters read the resolved literals. prometheus merges hosts that share
a label set, so the two nxos leaves come out as one target group, with an
`InstanceDown` alerting rule written beside them:

```json
{ "targets": ["198.51.100.101:9100", "198.51.100.102:9100"],
  "labels": { "job": "node", "platform": "nxos", "role": "leaf", "site": "fra1" } }
```

dns reads the same addresses and writes a forward and a reverse zone, and avd
renders that as an arista avd ansible project directory that has the same groups,
split across files, with the node-type tables assembled from the host objects
and the cabling.

```
avd/
├── inventory.yml       # all -> children {fra1 -> leaf, spine}
├── group_vars/         # all.yml, fra1.yml, leaf.yml, spine.yml
└── host_vars/          # leaf01.yml, leaf02.yml, spine01.yml, spine02.yml
```

i think this is the appropriate payoff of having to actually think of a data
model for your system: you get to feed it everywhere, and it’s cheap to add new
tools to your automation stack.

one last magic trick.

## swapping the source of truth

only the front of the pipeline is netbox-specific. everything from the map on is
not, so as a weekly ci run just for fun we seed the same fabric into
[infrahub](https://www.infrahub.app/) instead and ran the identical
`import -> map -> emit` chain. the artifacts come out byte-identical to
the netbox golden. make of that what you will (though we have thoughts on that
we will share in the future).

two things do change, both in the backend. netbox has fixed native models, so
`--provision` is close to a no-op while infrahub provisions *its own* schema out
of the ir, so the seed’s schema is what defines infrahub’s types. and infrahub
returns relationships as opaque backend ids, so import reduces each object to a
fixpoint before its references are uids. the engine does that settling, not the
adapter, which is why the references round-trip to the same uids netbox produces.
it’s a general feature of our infrahub adapter to make sure automation actually
works with it, but it’s important to mention, i think.

## proving the files are real

of course a golden diff only proves determinism, not validity and not that the
fabric runs. so as part of our ci, the artifacts are handed to the tools they were
emitted for, and each check assert something about the state rather than just
reporting nothing crashed. most of these tools accept an empty file happily
(ex: `promtool` reports `SUCCESS: 0 rules found`, and `ssh -G` answers for a
host it has never heard of).

so `ansible-inventory` has to give back four hosts under their role groups,
`InitNornir` each host’s *inherited* vars, `named-checkzone` four a records and
four ptrs, and so on. it’s the only way to make sure.

the avd project actually gets built with real `eos_designs`, and the device
configs go into a batfish snepshot where every bgp session batfish derives
(underlay ebgp, evpn overlay, mlag ibgp) has to come back `UNIQUE_MATCH`.
call us paranoid, but we just need to know.

and then for the final play.

the last check runs the loop backwards, for the four emitters that read their
own artifact (ansible, nornir, dns, prometheus). each committed file is imported
statelessly and replanned, the plan has to be `0 to create, 0 to update, 0 to
delete`, and the apply has to give the file back byte-identically. that’s, of
course, our brownfield check: point a reader at an inventory you already have
and get a model out.

this all has to be green, all of the time, because if it is, alembic is an
implementation of our vision.

## why

the individual tools are all fine. we’re not trying to shove a new system into
the mix.

what costs time is that the fabric is there nine times, and the copies drift
apart when life happens, as it does. if we create a model once and keep the
files purely its outputs the drift stops.

**disclaimer, again:** the engine and dcim/ipam adapters are open source under
apache-2.0. the connectors shown here are the commercial alembic ops layer,
external adapters speaking the same protocol as the free sdk (which means you
can add your own, and we encourage it). the cli installs with
`cargo install alembic-cli` or from [the releases
page](https://github.com/cyberwitchery/alembic/releases/). if you want to see
this run against your own source of truth, [get in touch](mailto:contact@cyberwitchery.com).

[^1]: this is also why the interface labels here read `Ethernet1` where the
diagrams post showed `eth1`. the seed still uses the short names, `map`
renames them.
