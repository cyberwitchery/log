---
title: "sbom-diff: comparing software bills of materials"
date: 2026-02-17
slug: sbom-diff
tags: [supply chain, tooling, release]
summary: "diff your sboms, catch surprises before they ship<br/>`cargo install sbom-diff`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/sbom-diff
    - label: docs
      url: https://docs.rs/sbom-diff/
    - label: crates.io
      url: https://crates.io/crates/sbom-diff/
---

sbom-diff compares software bills of materials across versions. it tells you
what changed: new dependencies, removed packages, version bumps, license
switches. the kind of things you want to know before cutting a release.

## why

sboms are important, sometimes even mandatory for software supply chain security.
but generating them is only half the story—you also need to understand what changed
between builds. did a transitive dependency sneak in a license change? did
someone vendor a new library without review?

most sbom tooling focuses on generation or vulnerability scanning. sbom-diff
fills the gap between: given two sboms, what's different? it also gives you knobs
for gates, what’s allowed and forbidden, etc.

## usage

basic comparison:

```bash
sbom-diff old.json new.json
```

output looks like:

```
summary: +3 added, -1 removed, 7 changed

+ lodash@4.17.21 (npm)
+ axios@1.6.0 (npm)
+ semver@7.5.4 (npm)
- moment@2.29.4 (npm)

~ express@4.18.2 → 4.19.0 (npm)
~ typescript@5.2.0 → 5.3.0 (npm)
  ...
```

markdown output for pr comments:

```bash
sbom-diff old.json new.json -o markdown
```

filter to specific change types:

```bash
sbom-diff old.json new.json --only version,license
```

fail the build if someone adds a gpl dependency:

```bash
sbom-diff old.json new.json --deny-license gpl-3.0-only
```

## format support

sbom-diff reads cyclonedx and spdx json files. it normalizes both to a common
internal representation before diffing, so you can compare across formats if
needed[^1].

component matching uses package urls (purls) when available, falling back to
name+ecosystem identity matching. this handles the common case where different
tools generate slightly different sboms for the same codebase.

## design choices

a few things that matter:

- **deterministic output**: same inputs, same output. always. makes it easy to
  use in ci where you might diff the diff.
- **zero network access**: no calling out to vulnerability databases or package
  registries. the tool does one thing and does it offline.
- **format-agnostic**: cyclonedx and spdx both have their quirks. sbom-diff
  abstracts over them so you don't have to care which one your generator emits.

## ci integration

the obvious use case is pr checks. generate an sbom in ci, compare it against
the baseline from main, post the diff as a comment. the `--deny-license` flag
lets you enforce license policy without a separate tool.

i'm using it in a github action that runs on every pr. catches dependency
changes that would otherwise slip through unnoticed.

[^1]: comparing cyclonedx against spdx for the same project is a good way to
find out how much your sbom generators disagree with each other.
