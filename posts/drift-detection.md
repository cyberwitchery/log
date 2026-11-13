---
title: "drift detection with alembic"
date: 2026-11-13
author: "Veit Heller"
slug: drift-detection
tags: [alembic, network automation, tooling]
summary: "netbox says one thing, dns another. how to find out what moved, and what to do about it.<br/>`cargo install alembic-cli`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/alembic
    - label: docs
      url: https://github.com/cyberwitchery/alembic/tree/main/docs
    - label: crates.io
      url: https://crates.io/crates/alembic-cli
---

**disclaimer:** the dns driver in this post is part of alembic ops, the
commercial layer on top of alembic. drift detection itself works with
any backend that reads.

maybe in your system netbox is where change starts. you readdress a device,
alembic carries the change out to everything downstream, and the dns server,
the monitoring and the inventories all follow.

that’s only true as long as nobody changes those other systems directly. but,
sooner or later someone always does: an `nsupdate` during an incident, a record
added for a test box, a host deleted because it looked unused, someone’s cat
walking across the keyboard.

this post is about finding those changes, and deciding what to do with each.

## the diff, already present

alembic doesn’t need a separate tool to find changes. every `plan` already does
three things: it observes the backend, matches what it observed to what you
declared, and diffs the matched pairs. the diff then produces the necessary
operations.

`plan --report` stops one step earlier. it takes the same diff and prints it as
a report instead of a list of operations. it writes no plan and saves no
state, so running it changes nothing.

the diff is purely additive. only fields you declared are being compared, so a
field from the backend that your model doesn’t mention is not drift. drift only
comes from the things we care about.

## three categories

every difference falls into one of three categories. with three dns records
changed by hand in a zone that alembic manages from netbox, for instances, it
could look like this:

```
$ alembic plan --backend-config dns.yaml -f zone.json --report -o drift.json
state: ./.alembic/state/external-2c284e24.json for external (127.0.0.1:5354/fra1.example.net.), 4 bindings
drift report: 1 changed, 1 missing, 1 extra

changed (present but diverged):
  dcim.device {"name":"leaf02"}
    primary_ip: "198.51.100.112" -> "198.51.100.102"

missing (declared in intent, absent from backend):
  dcim.device {"name":"spine02"}

extra (present in backend, not declared in intent):
  dcim.device {"name":"jump01"}
matching: 3 by state, 0 by key, 1 to create

drift report (json) written to drift.json
```

**changed** is a matchedpair whose declared fields differ. the arrow points
from the observed value to the declared one, so it reads as the update a plan
would make. **missing** is an absent observed object, **extra** is an unexpected
observed object.

## one way only

the report describes how the backend differs from the model, and not the
other way around. there is no mode that writes observed values back into the
model or the state store, and that’s deliberate.

if you really want it, and the adapters have the capabilities, you can always
just swap position. but drift is inherently directional, and we decided that
unidirectionality is a feature we want to keep.

this way, we get to choose: if the change downstream was a mistake, the next
apply removes it. if it was right, we can run the drift direction without
`--report`, and then apply it, and from then on it’s no longer drift.

the same diff runs once more at apply time. since 0.12.0, apply diffs the
plan’s objects against the backend again before it writes, and refuses if
anything moved since the plan was made. that’s drift detection closing the gap
between review and write, with the same machinery.

## fin

drift detection in alembic is just deployment backwards, without a final
application. there is real power in the idea that everything is just a
transformation, it turns out.

the cli can be installed with `cargo install alembic-cli` or downloaded from
[the releases page](https://github.com/cyberwitchery/alembic/releases/). if you
want to see this run against your own source of truth, [get in
touch](mailto:contact@cyberwitchery.com).
