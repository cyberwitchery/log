---
title: "alembic dev log, july 2026"
date: 2026-08-01
author: "Veit Heller"
slug: alembic-dev-log-2026-07
tags: [alembic, network automation, newsletter]
summary: "three releases, a see-before-write for schema, and files that refuse typos.<br/>`cargo install alembic-cli`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/alembic
    - label: docs
      url: https://github.com/cyberwitchery/alembic/tree/main/docs
    - label: crates.io
      url: https://crates.io/crates/alembic-cli
---

second issue of the [alembic](https://github.com/cyberwitchery/alembic)
dev log. the [june issue](/log/alembic-dev-log-2026-06) set the baseline, so
this one gets to be pure delta. if you don’t know what alembic is, start there.

## releases

three releases this month: **0.6.0**, **0.7.0**, and **0.8.0**. the first one
landed four days into the month and shipped everything that was on june’s
changelog on-deck list: format validation for `cidr`/`prefix`/`mac`/`slug`
fields, schema `ref` targets that must name a real type, and `map` rewiring
references nested inside `list`/`map` fields.

housekeeping note: since 0.7.0 the installed binary is `alembic`, not
`alembic-cli`. the crate name stays the same, so it’s still
`cargo install alembic-cli`.

## see-before-write, now for schema too

the biggest thematic change of the month. alembic’s promise has always been
that nothing is written before you see the plan, but schema provisioning
(custom types and fields the backend needs before data can land) used to
happen at apply time without a preview. that is wrong, so now:

- `plan` previews the schema provisioning `apply` would perform, read-only,
  and carries it in the plan json as `schema_preview`.
- destructive schema changes (deleting alembic-owned types or fields) are
  gated behind `--allow-delete`, the same flag that already gated object
  deletes. deleting a custom type cascades to its objects, so this gate
  matters.
- the external adapter protocol grew a matching read-only `preview_schema`
  method, and the python sdk (now 0.2.0) and the rust template both speak it.

much better.

## typos are errors now

0.8.0 starts a sweep i’d argue is overdue: **unknown keys in user-authored
files are rejected instead of silently discarded**. adapter configs came
first, where a typo’d boolean took the default and, in the worst case, loaded
an inventory into a database you didn’t mean to touch. the schema block
followed. the remaining surfaces (inventory files, the object envelope, the
map spec) are done on main and ship with the next release. i also made sure
that errors are descriptive enough to be useful when debugging. the ops-layer
adapters picked up the same treatment for their config blocks.

## scale & perf

erik built a synthetic plan generator for scale testing, and the engine got
measured against 50k-object workloads for the first time. results:

- a 50k-object inventory that previously could not `validate` within ten
  minutes now loads in under a second. line indexing was accidentally
  quadratic, sorry for the boo-boo.
- journal bookkeeping during apply went from `O(n²)` to `O(n)`.
- the local state store now takes an exclusive lock for the whole run, so two
  concurrent runs can’t silently clobber each other’s state mappings.

## adapters

- external adapters now self-report their role (observer, emitter, or full
  adapter) through a new `capabilities` protocol method, so an emit-only
  adapter errors cleanly on `plan`/`import` instead of observing nothing.
  0.6.0 also added `alembic-adapter-test`, a standalone conformance runner
  for external adapter executables.
- the django adapter got a month of overdue love: the generated app now
  actually loads the inventory (as a fixture), the generated rest api can
  create objects, filtering and search work, there’s an openapi schema at
  `/api/schema/`, and a schema that would generate a broken app is rejected
  up front with every offender named. it also got its missing reference page
  in the docs. all in all, it creates passable dcim/ipam systems now.
- `map` learned `emit: passthrough`, a catch-all that copies unmatched
  objects through unchanged. reshaping one field no longer needs an identity
  rule per type. less verbose mappings make my fingers happy.

## the ops layer

briefly, since it’s the commercial side[^1]: the containerlab adapter grew a
**drive mode** that reconciles a *live* lab, observing via `clab inspect`,
planning diffs against reality, and converging via containerlab’s own
primitives, with journaled, resumable applies. the dns adapter became a live
driver (zone transfer in, rfc 2136 dynamic updates out), several emitters
(ansible, nornir, prometheus, dns) learned to read their existing artifacts
back into the ir, an arista avd emitter joined for real, and ci now runs
[batfish](https://www.batfish.org) over the fabric’s generated configs.
both drive modes are gated in ci against the real thing: a live containerlab
lab, and a real bind primary for the dns driver. the resumable-apply
machinery gets driven through an actual injected failure there too.

i’ll demo it publicly soon, but we can drive a full fabric with observability
and all through plain alembic with ops plugins now, and it’s not a hassle.

## around alembic

in [netform](https://github.com/cyberwitchery/netform) we released 0.7.0 and
then spent the month on diff correctness (junos set-style identity, structure-aware
child diffing, numbered acl rule bodies). nautobot.rs and infrahub.rs tracked
their upstreams (nautobot 3.1.6, infrahub 1.10.0), and infrahub-erd 0.3.1
fixed generics rendering and unified its four output formats behind one
renderer.

we are still two patch versions behind netbox upstream on netbox.rs, a fact i
want to rectify this weekend. just missed the deadline for this dev log, but oh
well. can’t have it all.

## people

**[erik svedäng](https://www.eriksvedang.com)** shipped the erratic
fault-injection adapter’s journal resume
(the machinery from june’s resumable apply now proves itself under injected
failures) and the scale-testing generator mentioned above.

**[piya gehi](https://orgnizedmess.net/)** has started contributing. she’s working
on an [eve-ng](https://www.eve-ng.net) adapter, and on a general eve-ng
client library for rust to put underneath it. i’m very excited.

less people, but contributors: a good share of the month’s smaller fixes were
opened as prs by [heartbeat](/log/heartbeat), the org’s cyclical claude code
agent, and reviewed by yours truly before merge. it kept me busy.

## health

- the published walkthroughs and case studies now execute in ci, next to the
  fabric golden-file e2e from last month, so the documented flows are checked
  against the binary on every merge.

## on deck

- finishing the unknown-keys sweep across every user-authored file format
  (already on main).
- more of the same: the changelog’s unreleased section is where next month’s
  issue starts.
- docs, demos, connectors galore.

next issue at the end of august. see you then!

[^1]: same split as before: the ir, the engine, and the dcim/ipam connectors
are open source under apache-2.0. the fabric and ops connectors are the
commercial layer.
