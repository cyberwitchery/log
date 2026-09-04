---
title: "shopping for backends"
date: 2026-09-04
slug: shopping-for-backends
tags: [alembic, network automation, tooling]
summary: "in which we help out the imaginary person in charge of choosing a new dcim system"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/alembic
    - label: docs
      url: https://github.com/cyberwitchery/alembic/tree/main/docs
    - label: crates.io
      url: https://crates.io/crates/alembic-cli
---

picture this; you're the person in charge of picking a suitable dcim
system to keep track of you business' inventory. to get a good feel
for the new system, you want it filled up with a lot of *stuff*,
preferably with realistic configurations. instead of adding each
such thing manually via a web interface, wouldn't it be much nicer if
a tool did it for you? and ideally this tool would be driven by
backend-agnostic spec that could be reused for each potential system
that you want to try out? and what if someone had already created such
a spec, so you could just use it and modify it as you like?!

well, we got some good news for you; alembic can do just this (and
more). this blog post will show you how.

# the spec

to begin, we need a specification of what things to create in the
system. we could define this in an inventory file, with a
backend-agnostic schema (see the [docs]() on how to do this). or we
could just use one of the examples from the `alembic` repo,
e.g. [we_need_to_create_this_schema.yaml]().
