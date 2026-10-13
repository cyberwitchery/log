---
title: "one advisory, seven repos"
date: 2026-10-13
author: "Veit Heller"
slug: unsafe-libyaml
tags: [security, supply chain, ai]
summary: "in this post, we follow one unmaintained-crate advisory through the org, and what it took to retire it.<br/>`RUSTSEC-2024-0449`"
"links?": true
links:
    - label: the advisory
      url: https://rustsec.org/advisories/RUSTSEC-2024-0449
    - label: serde-saphyr
      url: https://github.com/bourumir-wyngs/serde-saphyr
    - label: alembic 0.11.0
      url: https://github.com/cyberwitchery/alembic/releases/tag/v0.11.0
---

this morning, `cargo deny` went red in divinate:

```
error[unmaintained]: unsafe-libyaml is unmaintained
   ├ ID: RUSTSEC-2024-0449
```

`unsafe-libyaml` is libyaml, machine-translated to rust. it is what
`serde_yaml` and its forks sit on. nothing in it is known to be broken, it
just isn’t maintained any more. this is the bad day from
[the secure defaults post](https://cyberwitchery.com/log/secure-defaults-ci.html),
working as intended: a red build, and nobody had to read a mailing list.

this post is about the cleanup, and about how it went with claude code doing
most of the legwork. by hand, i’d guess this is a few days of work. it took a
morning of wall-clock time, and [about an hour] of mine.

## how far it reached

seven of our sixteen rust repos had `unsafe-libyaml` in their lockfile. two of
them, netbox.rs and nautobot.rs, were still green, but only because their last
ci run was four days old. the next pr would have gone red.

the repos weren’t equally hard. the netbox and nautobot clis only write yaml,
for `--format yaml`, so that was one line each. two private repos parse their
config into typed structs, which made their swap mechanical. alembic was the
real job, more on that below. the python adapter sdk and the
[carp sqlite adapter](https://github.com/cyberwitchery/alembic-adapter-sqlite-carp)
needed nothing at all: they only see the adapter protocol, which is json on
stdin.

## the replacement

we moved to [serde-saphyr](https://github.com/bourumir-wyngs/serde-saphyr). it
is pure rust with no c underneath, which suits crates that `forbid` unsafe
code. the alternative was `serde_norway`, a maintained fork of the same
translated libyaml, and nearly drop-in. it would have been the smaller diff,
but i’d rather not do this twice.

## what changed without saying so

a dependency swap that compiles and passes its tests can still change what
your files mean. so for every affected repo we parsed every tracked yaml file
with the old and the new library and compared the results, then probed the
edges. the tracked files came out identical. the edges did not.

the worst one is this input, with the first line indented:

```
"  x: 1\ny: 2\n"

old: Err("deserializing from YAML containing more than one document is not supported")
new: Ok(Object {"x": Number(1)})
```

everything after the dedent is gone, and no error is raised. for an
inventory, objects that vanish from the input are objects the plan deletes.
someone had [reported it upstream](https://github.com/bourumir-wyngs/serde-saphyr/issues/219)
the day before. until it’s fixed, we read through the multi-document reader
and require exactly one document.

the others:

- yaml 1.1 booleans. parsed into an untyped value, `country: NO` becomes
  `{"country": Bool(false)}`, the old norway problem. typed string fields are
  fine, but alembic’s attrs are untyped, so it now only accepts `true` and
  `false` as booleans.
- error messages quote the surrounding lines of the source by default. that’s
  helpful for an inventory and less so for a config holding an api token. we
  turned it off.
- tags are dropped without a word: `x: !vault abc` reads as the plain string
  `abc`. where we re-render someone else’s file, a tag is now refused.

a few changes we accepted, such as `017` reading as a number and merge keys
merging. the changelog lists them.

none of these broke a test. i’d argue this is where most of the risk in a
dependency swap lives, and it is also where the help mattered most. running
two parsers over everything and diffing the results is tedious enough that i
probably wouldn’t have done it by hand.

## the api that named a yaml crate

alembic’s adapter sdk had this in its public trait:

```rust
fn setup(&mut self, configuration: &serde_yaml::Value) -> Result<(), Self::Error>;
```

so an advisory about a transitive crate became a breaking release for every
external adapter. it was also the second time, after an earlier move from
`serde_yaml` to `serde_yaml_ng`.

in 0.11.0, `setup` takes a `serde_json::Value`, which is what arrives over the
wire anyway. yaml reading and writing lives in one module in the sdk, and its
error type names no yaml library, so the next swap is a one-file change. it
is a minor bump because we are pre-1.0, and a patch release would have reached
every adapter on its next `cargo update` and stopped it compiling.

the first version put that module in the engine. the sbom gate showed our
adapters going from 74 to 158 components, tokio, postgres and openssl
included, just to read a config file. it moved to the sdk the same day[^1].

## where the time went

claude code did the sweep, the ports, the parser comparisons and the ci
watching, partly through subagents working in separate git worktrees. i made
the calls: which crate, whether a changed state fingerprint needed a
migration (it didn’t), 0.11.0 rather than 0.10.1, and when to push to main.
review stayed human.

it wasn’t frictionless. once it reported a batch of results without saying
what it had done to get there, and i had to ask[^2]. but most of the morning
was waiting on ci, a review and lunch, not on either of us.

what i keep coming back to is the parser comparison. compressing the
mechanical part from days to an hour is nice. the part i value more is that
the careful version of the work became cheap enough to actually do.

alembic 0.11.0 is on crates.io. if you maintain an external adapter, the port
is swapping `serde_yaml::Value` for `serde_json::Value` in `setup`, and the
changelog has the rest.

[^1]: the gate from the secure defaults post, earning its keep in the same
week we wrote about it.
[^2]: to its credit, it also caught and corrected a pr description of its own
that claimed a check had run against code it hadn’t.
