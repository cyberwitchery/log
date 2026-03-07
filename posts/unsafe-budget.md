---
title: "unsafe-budget: an unsafe code budget gate for ci pipelines"
date: 2026-02-22
slug: unsafe-budget
tags: [rust, go, supply chain, tooling, release]
summary: "keeps the unsafety demons out<br/>`cargo install unsafe-budget`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/unsafe-budget
    - label: docs
      url: https://docs.rs/unsafe-budget/
    - label: crates.io
      url: https://crates.io/crates/unsafe-budget/
---

`unsafe-budget` is a ci tool that tracks unsafe code in rust and go projects. it
fails your build when unsafe usage exceeds a budget you define.

## why?

unsafe code is sometimes necessary, like for ffi, performance-critical paths,
low-level system interactions. but it's also where memory safety guarantees
disappear. every `unsafe` block is a place where bugs can hide and audits need
to focus.

the problem isn't that unsafe exists, but when it grows without anyone
noticing. a dependency update pulls in a crate with more unsafe than you
expected. a refactor adds a few blocks here and there. before long, your
"minimal unsafe" codebase has drifted.

unsafe-budget makes this visible and enforceable. set a baseline, run it in ci,
get notified when someone tries to merge code that crosses the line.

## how it works

three commands cover the workflow:

```bash
# scan the project and print unsafe usage
unsafe-budget scan

# compare against baseline, exit 2 if budget exceeded
unsafe-budget check

# update the baseline (after intentional changes)
unsafe-budget update
```

the tool detects your project type from `Cargo.toml` or `go.mod` and picks the
right provider. providers are plugins that know how to count `unsafe` in a
specific ecosystem: `cargo-geiger` for rust, `go-geiger` for go[^1].

## modes

`unsafe-budget` supports two enforcement modes:

**ratchet mode** compares against a baseline file. unsafe can only go down,
never up. this is the default and works well for gradual reduction.

**caps mode** enforces explicit hard limits. useful when you have a specific
target or compliance requirement. ratchet probably turns into caps over time if
you take it seriously!

configure via `unsafe-budget.toml`:

```toml
mode = "ratchet"
include_deps = true

[caps]
default = 100
```

## ci integration

the exit codes are designed for pipelines: `0` for clean, `1` for errors, `2`
for budget violations. a typical github action looks like:

```yaml
- name: check unsafe budget
  run: |
    cargo install unsafe-budget
    unsafe-budget check
```

the `--format json` flag produces machine-readable output if you want to do
something fancier, like posting a diff to a pr.

## why not just cargo geiger?

`cargo-geiger` is great for one-off audits, but it doesn't remember, and
quality gates are harder to enforce. every run is independent—you see the
current count, not whether it went up or down since last week.

`unsafe-budget` wraps geiger (and other providers) with state management. the
baseline file tracks your budget over time. ci can enforce that unsafe never
increases without explicit approval. `--details` shows exactly where changes
happened. the baseline is content-addressed, so reorganizing code without
adding unsafe won't trip the check.

## extending it

any executable named `unsafe-budget-plugin-*` in your path becomes a provider.
this is how you'd add support for other languages or custom unsafe-like
patterns in your codebase[^2].

[^1]: go doesn't have an `unsafe` keyword in the same sense, but it does have
the `unsafe` package and cgo. go-geiger tracks both.

[^2]: i'm considering adding a provider for c/c++ interop auditing, but that's
a project for another day.
