---
title: "netform: lossless config diffing for network devices"
date: 2026-03-11
slug: netform
tags: [network automation, tooling, release]
summary: "parse and diff network configs, catch drift before it bites<br/>`cargo install netform_cli`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/netform
    - label: docs
      url: https://docs.rs/netform_ir/
    - label: crates.io
      url: https://crates.io/crates/netform_cli/
---

netform parses network device configurations into a lossless tree, then diffs
them. it tells you what actually changed between an intended config and what's
running on the box, without drowning you in noise from comment drift,
reordering, or whitespace.

## why

if you've ever diffed two router configs with `diff`, you know the pain.
reordered ntp servers show up as changes. comment banners generate walls of
red and green. you end up eyeballing hundreds of lines to find the three that
matter.

netform understands config structure. it normalizes away the noise you don't
care about and diffs what's left.

## quick start

```bash
# compare two ios xe configs, suppressing comment and reorder noise
config-diff --dialect iosxe --order-policy keyed-stable --ignore-comments intended.cfg actual.cfg

# json output for automation
config-diff --json intended.cfg actual.cfg

# transport-neutral remediation plan
config-diff --plan-json intended.cfg actual.cfg
```

as a library:

```rust
use netform_ir::parse_generic;
use netform_diff::{diff_documents, NormalizeOptions};

let intended = parse_generic("interface Ethernet1\n  description uplink\n");
let actual = parse_generic("interface Ethernet1\n  description downlink\n");
let result = diff_documents(&intended, &actual, NormalizeOptions::default());
```

## structure

six crates: an ir with a generic parser, a diff engine, three dialect crates
(arista eos, cisco ios xe, juniper junos), and a cli.

each dialect provides key hints that tell the diff engine how to match blocks
by identity, so `interface Ethernet1` and `interface Ethernet2` are recognized
as distinct blocks, not a rename[^1]. there's also a generic indentation-based
parser for configs that don't fit a specific dialect.

## design choices

- **lossless**: nothing is dropped. every line, comment, and blank survives
  parsing. `parse(render(doc))` is identity.
- **deterministic**: same inputs, same output. always.
- **explicit uncertainty**: when the engine isn't confident about a match, it
  surfaces that as a finding alongside the diff, no silently drops.

[^1]: without key hints, two interface blocks with different names but the same
position would be diffed against each other, producing misleading output.
