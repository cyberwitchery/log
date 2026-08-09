---
title: "nautobot to netbox, there and back again"
date: 2026-08-09
slug: nautobot-to-netbox
tags: [alembic, network automation, tooling]
summary: "the two tools don’t agree on a model. locations vs sites, status as a reference vs a string. a migration between them is a translation rather than an export. alembic has a map that does it.<br/>`cargo install alembic-cli`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/alembic
    - label: docs
      url: https://docs.rs/crate/alembic-cli/latest
    - label: crates.io
      url: https://crates.io/crates/alembic-cli
---

if you’ve ever tried to move data from one dcim tool into another, you already
know my pain. maybe you get a csv export if you’re lucky, in the source system’s
model. of course the target wants its own, as well it should. maybe the two look
like they mostly agree, but there are always fault lines, and they always cause
unnecessary friction.

in this blog post, we do a small but real migration from nautobot to netbox that
does the translation properly, with alembic’s [`map`](/log/alembic) step doing the
interpreter work.

## a tale of two models

despite originating from similar backgrounds, nautobot and netbox describe the same
fabric differently, and the differences aren’t just cosmetic. over time, the two
systems have diverged quite significantly!

- nautobot 2.x organizes locations as `dcim.location`, keyed by a human name,
  with no slug. netbox uses `dcim.site`, and the slug is required.
- nautobot models status as a *reference* to an `extras.status` object. netbox
  wants a status string.
- a device points at `location` in one and `site` in the other.

none of those are particularly bad in isolation. a simple python script would
probably be able to translate. but what i want to emphasize is that a migration
here is not export-then-import. there’s a translation step, and if you don’t
know both models you end up with garbage data in your target system.

in alembic, the data model and its flow are explicit. `import` (nautobot to ir),
`map` (ir to ir), then `plan` and `apply` (ir to netbox). the only step that
needs our attention is `map`.

we will go through all of them anyway, for completeness’ sake, and to show what
a real migration between real systems could look like.

## import: observe nautobot as it is

```bash
alembic import -o nautobot-ir.yaml \
  --backend-config backend-nautobot.yaml \
  -f schema-nautobot.yaml
```

`-f` is an inventory whose `schema` declares the nautobot-shaped types to
observe. import writes what it sees to `nautobot-ir.yaml`. trimmed to one
location and one device:

```yaml
- uid: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
  type: dcim.location
  key: { name: "Frankfurt DC1" }
  attrs:
    status: 99999999-9999-9999-9999-999999999999   # ref to extras.status
- uid: bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb
  type: dcim.device
  key: { name: leaf01 }
  attrs:
    status: 99999999-9999-9999-9999-999999999999
    role: leaf
    location: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
```

`status` is a uid pointing at an `extras.status` object, not the word `active`.
that’s nautobot’s model and we take it at face value for now. the job then is
to know how to say the same thing in netbox’s.

## map: rewrite into netbox’s vocabulary

`map` is a pure ir-to-ir transform. rules match objects by type, reshape them
through `${...}` templates, and follow references with `lookups`. two rules are
enough for this migration.

```yaml
rules:
  # dcim.location -> dcim.site: derive the slug netbox requires from the
  # location's human name, and resolve the status reference to a string.
  - name: locations-to-sites
    match: "dcim.location"
    lookups:
      status_name: { ref: "${attrs.status}", get: "key.name" }
    emit:
      type: dcim.site
      key:
        slug: "${key.name|slug}"
      attrs:
        name: "${key.name}"
        slug: "${key.name|slug}"
        status: "${lookup.status_name|lower}"

  # devices keep their type; the `location` relation becomes `site`.
  - name: devices
    match: "dcim.device"
    lookups:
      status_name: { ref: "${attrs.status}", get: "key.name" }
    emit:
      type: dcim.device
      key:
        name: "${key.name}"
      attrs:
        status: "${lookup.status_name|lower}"
        role: "${attrs.role}"
        # this ref is rewritten to the mapped target site
        site: "${attrs.location}"
```

given this translation layer as a spec file, we can execute:

```bash
alembic map -f nautobot-ir.yaml --spec map-nautobot-to-netbox.yaml -o netbox-ir.json
```

the output is in netbox’s vocabulary. `Frankfurt DC1` is now a site with slug
`frankfurt-dc1`, its status is the string `active`, and the device’s `site` ref
points at the new site:

```json
{ "type": "dcim.site",
  "key": { "slug": "frankfurt-dc1" },
  "attrs": { "name": "Frankfurt DC1", "slug": "frankfurt-dc1", "status": "active" } }
{ "type": "dcim.device",
  "key": { "name": "leaf01" },
  "attrs": { "role": "leaf", "site": "<new dcim.site uid>", "status": "active" } }
```

then it’s the usual read-only-then-write finish:

```bash
alembic plan  -f netbox-ir.json -o plan.json --backend-config backend-netbox.yaml
# check that everything looks right

alembic apply -p plan.json --backend-config backend-netbox.yaml
```

and we’re done!

## fault lines & safety

a rename that changes an object’s identity is where migrations tend to break.
why doesn’t this one?

two things:

- **the ref rewires itself.** deriving the slug changes the key, and therefore
  the uid, of every site. the device still lands on the right site because `map`
  rewrites references in a second pass, after every object’s new identity is
  known. you don’t thread the new uid through by hand, `map` sees that
  `locations-to-sites` is a 1:1 rename and follows it. nothing to do on your
  end, alembic handles it for you.
- **references become values.** nautobot’s `status` ref is resolved by the
  `lookups` block, which follows it to the status object and reads its name; the
  `lower` transform normalizes `Active` to `active`. a reference-valued field
  comes out as the plain string netbox expects. this is a simple transform once
  you know where to pull data from.

ids are recomputed from the target identity (`dcim.site` plus slug), so they’re
stable across runs, and netbox assigns its own backend ids on apply. this means
we also know an object’s provenance from the source system if we ever need it,
since we retain every system’s ids at every step.

in the end, every migration is a translation between two vocabularies for the
same model. in alembic, we write it down once as a map we can read, diff, and
run again, because that’s the power of being in control of the model.

this and many more examples live in the repository, and the cli can be installed
with `cargo install alembic-cli` or downloaded from [the releases
page](https://github.com/cyberwitchery/alembic/releases/).
