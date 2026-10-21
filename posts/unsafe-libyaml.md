---
title: "reacting to advisories in the age of llms"
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

this morning, the `cargo deny` ci gate went red in [divinate](https://cyberwitchery.com/divinate):

```
error[unmaintained]: unsafe-libyaml is unmaintained
   ├ ID: RUSTSEC-2024-0449
```

`unsafe-libyaml` is libyaml, machine-translated to rust. it is what
`serde_yaml` and its forks (we used `serde_yaml_ng`) sit on top of. nothing in
it is known to be broken, it just isn’t maintained any more. this is a bad
day from [the secure defaults post](https://cyberwitchery.com/log/secure-defaults-ci.html),
swooping in to prove its point 4 days later.

this post is about the cleanup, and about how it went with claude code doing
most of the legwork. by hand, i’d guess this is a few days of work. it took a
morning of wall-clock time, and about fifteen minutes of mine, not including
writing this self-congratulatory blog post.

## how far it reached

seven of our sixteen rust repos had `unsafe-libyaml` in their lockfile. the next
pr in any of them would have gone red.

the repos weren’t equally hard. the netbox and nautobot clis only write yaml,
for `--format yaml`, so that was one line each. two private repos parse their
config into typed structs, which made their swap mechanical. divinate simply
reads configs, and served as our canary for the change. alembic was a real job,
more on that below.

## the replacement

we moved to [serde-saphyr](https://github.com/bourumir-wyngs/serde-saphyr). it’s
pure rust with no c underneath, which suits crates that `forbid` unsafe code.
the alternative was `serde_norway`, a maintained fork of the same translated
libyaml, and nearly drop-in. it would have been the smaller diff, but i’d rather
not do this again.

we even encountered [our first
bug](https://github.com/bourumir-wyngs/serde-saphyr/issues/219) already, and
the turnaround time was reassuring.

## what changed

a dependency swap that compiles and passes its tests can still change your
semantics. so for every affected repo we[^1] parsed every tracked yaml file
with the old and the new library and compared the results, then probed the
edges. the tracked files came out identical. the edges did not.

the worst one is this input, with the first line indented, subject of the
issue above:

```
"  x: 1\ny: 2\n"

old: Err("deserializing from YAML containing more than one document is not supported")
new: Ok(Object {"x": Number(1)})
```

everything after the dedent is gone, and no error is raised. for an
inventory, objects that vanish from the input are objects the plan deletes.
until it’s released, we read through the multi-document reader and require
exactly one document. it’s good to do your diligence before publishing.

the other issues were easy to work around:

- yaml 1.1 booleans, the bane of my existence. parsed into an untyped value,
  `country: NO` becomes `{"country": Bool(false)}`, the old norway problem.
  typed string fields are fine, but alembic’s attrs are untyped, so it now
  only accepts `true` and `false` as booleans. yes, it’s part of the spec, no,
  don’t ask me about it.
- error messages quote the surrounding lines of the source by default. that’s
  helpful for an inventory and less so for a config holding api tokens or other
  sensitive data. we turned it off.
- tags are dropped, completely silently: `x: !vault abc` reads as the plain
  string `abc`. where we re-render someone else’s file, a tag is now refused.
  we documented it and moved on, since we don’t use tags ourselves.

a few changes we accepted, such as `017` reading as a number and merge keys
merging. the changelog lists them anyway, since we’re not the main consumer.

none of these broke a test. i’d argue this is where most of the risk in a
dependency swap is, and where i really do appreciate llm help. running
two parsers over everything and diffing the results is tedious enough that i
probably wouldn’t have done it by hand.

## the api with the yaml crate

alembic’s adapter sdk had this in its public trait:

```rust
fn setup(&mut self, configuration: &serde_yaml::Value) -> Result<(), Self::Error>;
```

so an advisory about a transitive crate became a breaking release for every
external adapter. it was also the second time, after an earlier move from
`serde_yaml` to `serde_yaml_ng`.

in 0.11.0, `setup` takes a `serde_json::Value`, which is what comes in over
the wire anyway. yaml reading and writing lives in one module in the sdk, and
its error type names no yaml library, so the next swap is a one-file change.

## where the time went

claude code did the sweep, the ports, the parser comparisons and the ci
watching, partly through subagents working in separate git worktrees. i prodded
it gently, explained  which crate, decided whether we need migrations (no),
0.11.0 rather than 0.10.1, and when to push to main (after i take a good hard
look at it). review stayed human.

it wasn’t frictionless. once it reported a batch of results without saying
what it had done to get there, and i had to ask[^2]. but most of the morning
was waiting on ci, a review and lunch, not on person or machine.

the main thing i took away from today is that tedium is still a bit tedious,
but 1-2x orders of magnitude less so, and i do my dependency swaps more
diligently than i would have before, not less.

alembic 0.11.0 is on crates.io. if you maintain an external adapter, the port
is swapping `serde_yaml::Value` for `serde_json::Value` in `setup`, and the
changelog has the rest.

[^1]: by which i mean my ai agent, while i was reviewing other prs.
[^2]: i find that in long-running tasks, the final message sometimes comes out
garbled as the agent forgets what it was that you had last said. i’m sure it’ll
get better again. somehow it always does.
