---
title: "alembic: a data-model-first dcim/ipam converger"
date: 2026-03-04
slug: alembic
tags: [network automation, tooling, release]
summary: "sync your infrastructure data across netbox and nautobot<br/>`cargo install alembic-cli`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/alembic
    - label: docs
      url: https://docs.rs/alembic/
    - label: crates.io
      url: https://crates.io/crates/alembic/
---

alembic is the project i've been building [netbox.rs](/log/netbox.rs) and
[nautobot.rs](/log/nautobot.rs) for. it's a data synchronization tool that lets
you define your dcim/ipam data once and converge it across multiple backends.

## the problem

if you've managed network infrastructure at scale, you know the pain: data lives
in spreadsheets, wikis, ticketing systems, and maybe a dcim tool or two. keeping
them in sync is manual, error-prone, and often just doesn't happen.

alembic takes a different approach. you define your infrastructure in yaml files
using a vendor-neutral intermediate representation (ir). alembic then figures out
what needs to change in your backends and generates a plan. you review it, apply
it, done.

## how it works

the core workflow is three commands:

```bash
# validate your yaml files against the schema
alembic validate ./infra/

# generate a plan comparing desired state to what's in netbox
alembic plan --backend netbox --url $NETBOX_URL --token $TOKEN ./infra/

# apply the plan (creates and updates only by default)
alembic apply plan.json
```

plans are deterministic json files. you can diff them, review them in prs, or
feed them into approval workflows. destructive operations require an explicit
`--allow-delete` flag.

## the intermediate representation

the ir is intentionally simple. here's a site with a device:

```yaml
- uid: site-dc1
  type: dcim.site
  key: DC1
  attrs:
    name: DC1
    status: active
    region: us-east

- uid: device-spine01
  type: dcim.device
  key: spine01.dc1
  attrs:
    name: spine01
    site: site-dc1  # reference by uid, not backend id
    device_type: arista-7050sx
    role: spine
```

references use uids, not backend-specific ids. alembic maintains a state file
(`.alembic/state.json`) that maps uids to backend ids, so renames and moves
work correctly.

## supported backends and entities

currently alembic supports netbox and nautobot[^1], with the following entity types:

- `dcim.site`, `dcim.device`, `dcim.interface`
- `ipam.prefix`, `ipam.ip_address`

relationships are validated at plan time: you can't assign an interface to a
device that doesn't exist, or bind an ip to an interface that isn't in the plan.

## architecture

the project is split into five crates:

- `alembic-core`: type definitions and validation
- `alembic-engine`: planning, graph validation, state management
- `alembic-adapter-netbox`: netbox backend (uses [netbox.rs](/log/netbox.rs))
- `alembic-adapter-nautobot`: nautobot backend (uses [nautobot.rs](/log/nautobot.rs))
- `alembic-cli`: the command-line interface

this makes it straightforward to add new backends or embed the engine in other
tools.

## what's next

the immediate roadmap includes richer types, a `diff` command for inspecting
drift without generating a full plan, and better error messages when validation
fails. longer term, i'm exploring bidirectional sync and conflict resolution for
environments where multiple sources of truth need to coexist, and maybe config
generation.

[^1]: adding a new backend is mostly mechanical—implement the adapter trait and
map the ir types to the backend's api.
