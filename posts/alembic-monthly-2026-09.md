---
title: "alembic dev log, september 2026"
date: 2026-10-01
author: "Veit Heller"
slug: alembic-dev-log-2026-09
tags: [alembic, network automation, newsletter]
summary: "0.10.0, a first demo, and alembic inside netbox and nautobot.<br/>`cargo install alembic-cli`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/alembic
    - label: docs
      url: https://github.com/cyberwitchery/alembic/tree/main/docs
    - label: crates.io
      url: https://crates.io/crates/alembic-cli
---

fourth issue of the [alembic](https://github.com/cyberwitchery/alembic)
dev log. september brings **alembic 0.10.0**, released on september 27, a new
set of plugins that run alembic from inside a source of truth, and the first
public demo video.

## demo i: a fabric

we recorded [a first demo video](https://www.youtube.com/watch?v=c6Ap86rgt8M).
in about ten minutes it takes a simple fabric from just a running system in
containerlab to an automated and observable network using the netbox/nautobot
plugins.

i promised a public demo back in july, so i’m glad it’s out. sorry it took so
long.

## alembic in your source of truth

a new repo appeared! it’s
[alembic-sot-plugins](https://github.com/cyberwitchery/alembic-sot-plugins).
it holds a netbox plugin (`netbox-alembic`, netbox 4.6 or later) and a nautobot
app (`nautobot-alembic`, nautobot 3.2 or later), both on pypi as of this week,
on top of a shared core that runs the `alembic` cli and owns the run state.

the idea is that alembic’s loop should be usable by people who live in the
source of truth, not just the terminal. a run looks like this:

- `plan` runs as a background job, and the plan shows up in the ui for review.
- someone other than the requester approves it. in nautobot that is nautobot’s
  own approval workflows.
- before `apply`, the plugin checks that the target hasn’t moved since the
  plan was made, and then applies exactly the approved plan.
- a failed apply resumes from alembic’s journal.

a flow can also import from a source backend and reshape the data with a `map`
spec, so netbox or nautobot can be the source and another system the target.
drift runs record how a target differs from the inventory without going through
approval. any alembic plugin on the host shows up next to the built-in
connectors.

secrets stay out of the database, of course. a backend stores the name of a
credential, and the worker reads the value from its environment at run time.
commands and plugin configs come from files on the host, so whoever can edit a
backend in the ui cannot run a program on the worker. this is not necessarily
the most full-service flow yet, but we did not want to impose our own secret
storage on people.

docs are on [read the docs](https://alembic-sot-plugins.readthedocs.io/).

## 0.10.0

this release is mostly about netbox and nautobot telling us about themselves
instead of us poking at them with a stick.

- both adapters now read each type’s fields from the endpoint’s OPTIONS
  metadata. in netbox that fixed a bug that happened to not have bit us yet:
  netbox ignores unknown keys, so a field a type didn’t have was dropped on
  write and then showed up as drift forever. sounds pretty bad, right?

  `plan` now fails and names the field instead. in nautobot, a native field
  on a type with no objects yet is written as the field it is, not provisioned
  as a custom field.
- the netbox adapter also provisions a declared non-native field as a custom
  field. against netbox 4.6 and 4.7 it didn’t, because we spelled
  netbox’s feature name differently than netbox does. i chalk it up to sleep
  deprivation.
- the nautobot adapter takes each type’s route from the api root rather than
  deriving it.
- a plan that doesn’t need to adopt objects by key only reads the objects
  already bound in state, which narrows the queries against netbox, nautobot,
  and infrahub.
- a map spec takes an `objects:` a list of target objects with no source
  models, like a location type every mapped site shares. rules reference them
  by uid. this is useful for objects that don’t come from anywhere, but need to
  go in the target for all the relations and models to line up.
- every `-o` written to a `.yaml` path is now yaml. it used to be json under a
  yaml name, with a warning, which is the dumbest idea ever in hindsight.
- the shipped examples converge against netbox 4.2 and later.

erik moved the rust sdk for external adapters out of `alembic-engine` into its
own crate, `alembic-adapter-sdk`. it carries the protocol types, the apply
journal, and the retry driver, and the dependency profile is a bit lighter on
our consumers. the
[template](https://github.com/cyberwitchery/alembic-adapter-template) and the
python sdk both build and test against 0.10.0.

## the ops layer

briefly, since it’s the commercial side, and we don’t want to make the dev log
a sales pitch:

- erik wrote **alembic-controller**, a small program that runs the cli for you.
  its first feature is chatops: it posts a summary of a plan to slack, waits
  for someone to press approve or deny, and applies only on approval. discord
  is next, for all those many infrastructure providers running on discord.
- alasdair extended the batfish check over the fabric’s generated configs. it
  now requires batfish to report exactly the bgp sessions implied by the avd
  project, none missing and none spurious. during his work on that we also
  realized that the avd connector presupposes too much about your network
  topology. he’s on that next.
- piya’s eve-ng adapter now sits on
  [eveng.rs](https://github.com/orgnizedmess/eveng.rs), the eve-ng client
  library she wrote and published this month (yay, piya!). the adapter is in
  review.
- the prometheus emitter learned to emit the scrape config, and the ops
  adapters now build on the new sdk crate.

## around alembic

netbox.rs caught up with upstream and then some: it tracks netbox 4.7.1 now
(0.9.0, 0.9.1). nautobot.rs tracks 3.2.5 (0.7.0, 0.8.0) and takes filters as
one params struct instead of a long list of positional parameters, which
started to get unwieldy to users of the low-level crates. infrahub.rs follows
infrahub 1.11.3. [netform](https://github.com/cyberwitchery/netform)
released 0.10.0, which makes every dialect a module in one registry crate.
it’s getting pretty cool, you should check it out.

next issue at the end of october. see ya!
