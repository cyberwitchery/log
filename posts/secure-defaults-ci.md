---
title: "secure defaults as ci"
date: 2026-10-09
author: "Veit Heller"
slug: secure-defaults-ci
tags: [security, supply chain, tooling]
summary: "in this post, we examine the ci we run in every repo.<br/>`cargo install sbom-diff unsafe-budget`"
"links?": true
links:
    - label: sbom-diff
      url: https://github.com/cyberwitchery/sbom-diff
    - label: unsafe-budget
      url: https://github.com/cyberwitchery/unsafe-budget
    - label: cargo-deny
      url: https://github.com/EmbarkStudios/cargo-deny
---

last year i [wrote on my personal blog](https://blog.veitheller.de/Secure-by-default_over_Manuals.html)
that defaults and guardrails are cheaper and scale better than manuals and
training. i won’t make that argument again here.

this post is what’s missing from that argument, which is the action. in this
post, we walk through the ci we actually run in every cyberwitchery repo, gate
by gate, in a form you can paste, modify, and own. it is rust-shaped, because
we are. the shape should transfer beyond the ecosystem, however. if you want us
to share our python setup in a similar manner, let us know!

## the skeleton

every repo’s `ci.yml` has the same jobs: `fmt`, `clippy` with `-D warnings`,
`test`, `doc`, `deny`, `coverage`, whatever gates that repo needs, and then one
more:

```yaml
  success:
    name: success
    needs: [fmt, clippy, test, doc, deny, coverage, unsafe-budget, sbom]
    runs-on: ubuntu-latest
    if: always()
    steps:
      - name: check results
        run: |
          if [[ "${{ contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled') || contains(needs.*.result, 'skipped') }}" == "true" ]]; then
            exit 1
          fi
```

`success` does no work. it’s plumbing that exists for automation, such that
exactly one gate exists to point branch protection at when you wire it up[^1].

## every dependency all of the time

`cargo deny check` runs in every rust repo we release from. the config is boring
(that’s a good thing):

```toml
[licenses]
version = 2
allow = ["MIT", "Apache-2.0", "BSD-3-Clause", "CDLA-Permissive-2.0", "ISC", "Unicode-3.0"]

[sources]
unknown-registry = "deny"
unknown-git = "deny"
allow-registry = ["https://github.com/rust-lang/crates.io-index"]
```

the job is four steps:

```yaml
  deny:
    name: deny
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: dtolnay/rust-toolchain@7e38f4b43b4db5c8dd498af069a4f6196df1d067 # v1
        with:
          toolchain: stable
      - uses: taiki-e/install-action@83ac0ad63c0167e6f06796fab0fce28db1bf3db0 # v2.87.22
        with:
          tool: cargo-deny
      - run: cargo deny check
```

those are horrible hashes on purpose, more on that [below](#the-ci-itself).

a good day looks like this, and nobody reads it:

```
advisories ok, bans ok, licenses ok, sources ok
```

a bad day looks like the one we had in september. rustls shipped
[RUSTSEC-2026-0285](https://rustsec.org/advisories/RUSTSEC-2026-0285), and it
reached us transitively through `reqwest`, in every client crate we maintain
at once:

```
error[vulnerability]: TLS 1.3 handshake messages incorrectly accepted across encryption level boundaries
    ┌─ Cargo.lock:134:1
    │
134 │ rustls 0.23.40 registry+https://github.com/rust-lang/crates.io-index
    │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ security vulnerability detected
    │
    ├ ID: RUSTSEC-2026-0285
    ├ Solution: Upgrade to >=0.23.45 (try `cargo update -p rustls`)
    ├ rustls v0.23.40
      ├── hyper-rustls v0.27.9
      │   └── reqwest v0.12.28
      │       ├── netbox v0.9.0
```

exit code 1, build red, nobody had to be watching a mailing list. that is the
whole value add: the control is a default, and it started annoying me while i
was working on something else, blissfully unaware that there was an issue.

it makes everything red, so it’s quite aggressive. we run infra and security
tooling, so it’d honestly be a bit ironic if we didn’t do this. you might want
to be less aggressive, especially if your team is bigger than two, occasionally
three people.

one maintenance note: `cargo-deny` warns when an allowed license doesn’t match
anything in the graph. those warnings accumulate. we cut the stale entries out
of the client crates in september. it took ten minutes and should probably be
on a calendar, but i’m not that disciplined. maybe some day.

## the accidental dependency

`cargo deny` tells you a dependency is known-bad, but not that it’s new to the
project. for that every repo commits an approved sbom per package to `sbom/`,
and a shared workflow in our `.github` repo diffs against it using
[our own tool](https://cyberwitchery.com/log/sbom-diff.html). the call site is
short:

```yaml
  sbom:
    name: sbom
    uses: cyberwitchery/.github/.github/workflows/sbom.yml@64ffd6a08c3e9626a681c8be1c8ad056765f3b85 # main
    with:
      mode: report
```

on a pull request it generates a cyclonedx sbom per package, writes the diff
against the last release tag into the job summary, and warns about every
component that isn’t in the approved baseline. on a tag push, `mode: release`
turns those warnings into a failure, so nothing ships with a dependency nobody
approved. the tool versions are pinned as well, because a new `cargo-cyclonedx`
changes what counts as a component, and a baseline only means something if it
was generated the same way.

here is `sbom-diff`’s own last release, 0.8.0 to 0.9.0, a release that shipped
cyclonedx 1.6 support and a pile of parser fixes (generated before we added
`--target all`, hence the smaller numbers):

```
Diff Summary
============
Old total:        104 components
New total:        104 components
Unchanged:        97
Added:            0
Removed:          0
Changed:          7
Edge changes:     1

[~] Changed
-----------
pkg:cargo/indexmap@2.14.2
  Version: 2.14.0 -> 2.14.2
  Hashes:
    ~ sha-256: d466e945…49d9 -> cc4e190f…4c855
```

a patch bump of one transitive dependency and one new edge to a crate that was
already somewhere in the graph. from the supply chain’s point of view, a totally
ordinary month. also legible to any compliance work you’ll ever need to do in
the sbom space.

and here is what one line in a `Cargo.toml` looks like. if i add `ureq = "3.4.2"`
right now and diff against the committed baseline, i get this:

```
error: added component pkg:cargo/rustls@0.23.45 (--fail-on added-components)
error: added component pkg:cargo/ring@0.17.14 (--fail-on added-components)
error: added component pkg:cargo/webpki-roots@1.0.9 (--fail-on added-components)
…
Diff Summary
============
Old total:        129 components
New total:        162 components
Added:            33
```

exit code 3. one dependency, thirty-three components, including a tls stack, a
compression library, and ten crates that only exist for windows targets. seems
a lot scarier that way, but maybe it should. at least this way i actually think
about what i’m adding to my dependency graph.

again, a maintenance note: approving a dependency means committing the new sbom
as the baseline. until then the pull request carries a warning and the release
refuses to go out. i’d argue that puts the friction in the right spot: you read
the list once, when you accept it. you do have to actually read it, though.

## budgeted unsafe

where a crate can simply refuse unsafe code, the cheapest control is the lint
table:

```toml
[lints.rust]
unsafe_code = "forbid"
```

that is what `contextual-encoder` does, because a security library that
introduces unsafe code better have a real good reason to do so (and we don’t).
for every other kind of tool there is a budget, checked against a committed
baseline, again via [a house tool](https://cyberwitchery.com/log/unsafe-budget.html):

```yaml
  unsafe-budget:
    name: unsafe-budget
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: cyberwitchery/unsafe-budget@d10776ba7fe8043f31b19ec40bcff26b4da6b94e # v0.5.1
        with:
          mode: check
          version: v0.5.1
```

```
unsafe-budget check
===================
Analyzer: rustc_unsafe_lint

Status: PASSED

Totals:
  Workspace: 0 unsafe
  Dependencies: 0 unsafe
  Overall: 0 unsafe
```

the baseline lives in `unsafe-budget.lock`, so the number can only go down
without someone deliberately updating it. ratchet mode is the one we tend to
use. caps mode, where you name an explicit ceiling instead, makes more sense
in a codebase that has real unsafe to manage (not ours if i can help it).

## a floor instead of a target

coverage is a gate too, with a number per repo:

```sh
cargo llvm-cov --workspace --all-features --lcov --output-path lcov.info --fail-under-lines 80
```

the floors differ per repo, anywhere from 70 to 95 percent. 95 percent is,
again, `contextual-encoder`, because an encoder whose entire job is getting
escaping right needs more scrutiny than [a local cli for a lepiter knowledge
base](https://github.com/cyberwitchery/lepiter-cli). a single org-wide
percentage usually strikes me as theatrical, and the metric starts to invite
gaming it. sure, i could have checked all the cli entrypoints, but what
assurance does that really give us?

## the ci itself

every gate above runs other people’s code with access to our repositories, so
the workflows get two of their own defaults. every action is pinned to a commit
hash, with the tag kept as a comment for humans. and every job gets only the
permissions it asks for. ci workflows start from read-only:

```yaml
permissions:
  contents: read
```

release workflows start from nothing and grant per job, so the job that mints
attestations is the only one that can attest:

```yaml
permissions: {}

jobs:
  attest:
    name: attest
    needs: sbom
    uses: cyberwitchery/.github/.github/workflows/attest.yml@64ffd6a08c3e9626a681c8be1c8ad056765f3b85 # main
    permissions:
      contents: read
      id-token: write
      attestations: write
```

the same goes for the job that publishes the release, which is the only one
allowed to write to the repository. a tag can be moved after you review it, a
hash cannot (i suppose it could theoretically, but that’s not in the threat
model). dependabot bumps the hashes weekly along with everything else, so
pinning is handled by the machine at the cost of a pr i can approve from
bed.

## releases

every release generates a cyclonedx sbom per crate, checks it against the
approved baseline, attests the package and its sbom, and attaches the sbom to
the github release. that means anyone consuming our crates can check where a
package was built and run the same comparison we do, without asking us for
anything.

you may call it overengineering, but a few years of tech due diligence work
really made me crave automated checks and documentation. call it too many stale
notion pages in my past.

## missing pieces

you might spot a few missing pieces.

- we do no secret scanning or static analysis of our own. github’s secret
  scanning, push protection and codeql default setup are on for every public
  repo, and i have not felt the need to add a second layer[^2]. the dependency
  bumps are dependabot’s too, not ours.
- there is no container scanning, because we ship crates and binaries.

none of this is clever, because i enjoy boring security measures. every one of
these is under fifteen lines of yaml at the call site and a bunch of standard
(or in-house) tooling.

still, it lets us rest easy, and it doesn’t get any better than that.

[^1]: ours is not, currently. branch protection on our repos requires a review,
not a check. success is, as such, mostly hygiene.
[^2]: we have something in our collective back pocket here, but it’s not ready
for public consumption just yet. keep checking this log.
