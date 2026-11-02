---
title: "alembic dev log, october 2026"
date: 2026-11-02
author: "Veit Heller"
slug: alembic-dev-log-2026-10
tags: [alembic, network automation, newsletter]
summary: "0.11.0 and 0.12.0: a consolidation month, making the pieces fit together.<br/>`cargo install alembic-cli`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/alembic
    - label: docs
      url: https://github.com/cyberwitchery/alembic/tree/main/docs
    - label: crates.io
      url: https://crates.io/crates/alembic-cli
---

fifth issue of the [alembic](https://github.com/cyberwitchery/alembic)
dev log. october brings two releases, **0.11.0** on october 13 and **0.12.0**
on october 26. both have mild breaking changes, more on that below.

i’d call october a cleanup and consolidation month. there aren’t as many new
features as in the last few issues. most of the work went into making the
features we have nest and compose, and behave correctly in various
circumstances. less exciting to write up, but just as important.

## the plan you saw is the plan you get

plans are static artifacts. they are generated once, and can be applied later.
until 0.12.0 that was a bit of a silent footgun, because if you generated and
approved a plan and applied it later, apply adhered to the plan even if someone
had changed the backend in between. that gets more likely the further plan and
apply drift apart, which becomes visible in review flows like the source-of-truth
plugins and the gitops work we’ll talk about below.

now apply checks first. before it writes anything, it confirms that every
planned update’s `from` values still hold, that no planned create already
exists, and that nothing it means to update is gone. if any of that fails, it
refuses. `--no-stale-check` skips it if you really want to[^1].

two smaller apply changes also made it:

- `apply --only <uid>` (or `--only-file`) applies the operations of the named
  uids and nothing else. ideal for selective upgrades.
- a plan now records its `effects`, `emit` for a write-only backend and `drive`
  for one alembic reads and writes.

## exit codes

0.12.0 also makes exit codes semantically meaningful, part of our work on
making it usable in a pipeline. all the various exit scenarios now have a clean,
documented, unique exit code.

## a new yaml reader

0.11.0 replaced the unmaintained libyaml binding with `serde-saphyr`. i wrote
about [how we handled that advisory](/log/unsafe-libyaml) earlier this month,
so here’s just what changes for you:

- a duplicate key is an error in every mapping, including `attrs`.
- `017` and `1_000` read as numbers, not strings. quote them if you meant
  strings.
- `.inf` and `.nan` are refused.
- yaml output quotes strings that would read back as something else, like
  `"no"`.
- an external backend without `instance:` gets a new fallback identity, and
  with it a fresh state file. pin `instance:` if you want an identity that
  survives config edits.

## adapters and planning

some highlights:

- `plan` breaks reference cycles among new objects. netbox’s
  device → `primary_ip4` → ip → interface → device used to stop with
  `unresolved references`, now it works.
- first-contact adoption handles objects keyed by a ref, like an interface
  keyed by its device. those used to be planned as creates.
- the netbox adapter provisions an `enum` custom field as a `select` over a
  choice set, so netbox enforces the values. `plan` also fails on a custom
  field name netbox would reject, instead of writing a plan apply refuses.
- the nautobot adapter now converges the id of a generic foreign key instead
  of planning an update on every run.
- `plan` and `apply` say which state they loaded and how each declared object
  matched (by state, by key, adopted, or to create).
- `apply -p -` reads a plan from stdin, so `plan --dry-run` pipes straight
  into it.

## journals for more than one worker

erik moved apply journals out of the local directory into a configurable place.
with the postgres state backend, journals now live in the same database, so any
worker that uses it can resume an interrupted apply. with file storage,
`ALEMBIC_JOURNAL_DIR` does the same thing.

he also added `alembic completion` for shell completions and taught the file
generator to spread interfaces over devices and cable them up, which makes the
synthetic inventories we test with a lot more realistic.

## gitops, in progress

erik is also building a gitops flow for alembic on gitlab ci (he’s a machine).
it isn’t public yet, but the shape is there, i think. a workspace repo holds
the source of truth config, the targets, and their map specs, and a shared
pipeline runs `import` → `map` → `plan` → `apply` over it.

every change goes through a merge request. the pipeline commits each target’s
ir and plan onto the branch and posts the plans to the merge request, so you
see what will change outside the repo, and then you can approve. it’s quite a
nice little workflow!

more about it when it ships! probably in the next issue at the end of november.
see you then!

[^1]: the netbox and nautobot plugins pass it because they already run their
own stale check before apply. there are some legitimate reasons to not do the
generic version!
