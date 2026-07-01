---
title: "alembic dev log, june 2026"
date: 2026-07-01
slug: alembic-dev-log-2026-06
tags: [alembic, network automation, newsletter]
summary: "a monthly log of what moved in alembic and the tools around it. this first issue sets the baseline.<br/>`cargo install alembic-cli`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/alembic
    - label: docs
      url: https://github.com/cyberwitchery/alembic/tree/main/docs
    - label: crates.io
      url: https://crates.io/crates/alembic-cli
---

i’m starting a monthly note on what moved in
[alembic](https://github.com/cyberwitchery/alembic) and the
tools around it, published the first day of each month. this first issue is a
baseline: where things stand at the end of june 2026, so from july on i can just
report the delta. i’ll keep these short.

## what alembic is

i’ve [written](/log/alembic) and [talked](https://www.youtube.com/live/cpUmS0Ll3iM?si=7ZTqqBp51QMdoB4d&t=10942)
about alembic, but since then, almost 3 months have passed, and that’s about
fourty-five years in alembic time, so let’s pretend this is a first unveil.

i’ve taken to calling alembic the **connective tissue of your network automation
pipeline** or **the edges between your boxes**. what does this mean?

most systems in the network automation space are boxes. they are sources of
truth, or orchestrators, or observability tools. those are important, but we
tend to forget about the arrows between those boxes when we draw the diagram:
how does data actually flow from one system to the next?

this is what alembic does. it’s the layer between the elements of your stack,
the aether that flows between your components. and it speaks your own data
model, not that of any vendor.

sounds pretty cool, right? i think so.

## where it stands

cliff’s notes:

- alembic transforms data from a source of truth into a canonical,
  vendor-neutral ir, validates it, and converges that model onto one or more
  backends. it works on the edges between systems, not inside any one of them.
- latest release: **0.5.0**, on crates.io (`cargo install alembic-cli`).
- the loop is the same every time: `validate` → `import` → `map` → `plan` →
  `apply`. pull, map, and plan are read-only; `apply` is the only step that
  writes, and it writes a deterministic plan you’ve already seen.
- `map` is the powerhouse that transforms and shapes the data on the way.
- i have case studies of migrations between ipam/dcim systems
  (`infrahub<->netbox`) and full pipelines
  (`data->netbox->containerlab,ssh,prometheus,grafana`). it just works.

## the engine today

- **map** is a pure ir→ir transform layer: rules select objects by type and
  predicate, reshape them through `${...}` templates, rewire references across
  renames, and can call user-defined [starlark](https://github.com/bazelbuild/starlark)
  transforms. it also does `group_by` aggregation and `lookups` across refs.
  because it’s pure, maps chain.
- **`plan --report`** prints a read-only drift report (changed / missing /
  extra) without writing anything.
- apply is deterministic and topologically ordered; deletes stay gated behind
  `--allow-delete`.
- state lives in a local `state.json` or postgres, mapping stable uids to
  backend ids so renames don’t churn.

## adapters

- **open core**, in the repo: netbox, nautobot, infrahub (read + write),
  generic rest, peeringdb (read-only), and django (emit) if you want your own
  dcim api.
- **commercial ops layer** (alembic-ops): emitters that carry the same ir out to
  ansible, nornir, dns, prometheus, ssh, containerlab, and graphviz/mermaid
  diagrams. it’s a separate, paid layer, so i’ll only mention it here where it
  touches the open core[^1].
- **extension**: any of the above can also be an *external adapter*, a process
  alembic spawns that speaks json over stdio (protocol version 1). this month i
  shipped two front doors for writing one: a python sdk
  ([`alembic-adapter-sdk`](https://pypi.org/project/alembic-adapter-sdk/)) and a
  rust [template repo](https://github.com/cyberwitchery/alembic-adapter-template).
  and to prove that it works, i wrote [a full adapter in carp, a programming
  language i co-maintain](https://github.com/cyberwitchery/alembic-adapter-sqlite-carp/),
  in less than 250 lines of code.

## people

one professional contributor works on alembic alongside me, and we’re onboarding
two more. yes, people get paid to work on alembic.

**[erik svedäng](https://www.eriksvedang.com)** works across the engine and the ops layer. he built the
journal-backed resumable apply: an `apply` that dies partway through resumes
from where it stopped instead of redoing its writes, alongside a run of
correctness and performance fixes (including turning an o(n²) path into o(n)).
in the ops layer he wrote the containerlab connector and “erratic”, a
fault-injection adapter whose whole job is to make the resumable-apply
machinery prove itself.

## health

- june was the biggest month so far: **0.4.0** and **0.5.0** both shipped.
  0.4.0 retired the old raw-yaml→ir compiler and replaced it with `map`; 0.5.0
  taught the netbox adapter to handle generic foreign keys in both directions
  (a breaking change to a few ir field names).
- the “one source, many artifacts” fabric pipeline runs as a golden-file e2e in
  ci: it boots a real netbox, runs `seed → import → map → emit`, and diffs every
  generated file against a committed baseline. that’s the regression net behind
  the claim that one model feeds every tool.

## on deck

- public demos, case studies, and war stories are being prepared as we speak!
- from the unreleased changelog: format validation for `cidr`/`prefix`/`mac`/
  `slug` fields, stricter checks that schema `ref` targets name a real type, and
  `map` rewiring references nested inside `list`/`map` fields.
- more reference external adapters, now that the two sdks make them cheap to
  write.

next issue at the end of july.

[^1]: the split is deliberate: the ir, the engine, and the dcim/ipam connectors
are open source under apache-2.0; the fabric and ops connectors are where the
commercial side lives.
