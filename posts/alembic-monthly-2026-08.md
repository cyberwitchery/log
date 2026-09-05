---
title: "alembic dev log, august 2026"
date: 2026-09-01
author: "Veit Heller"
slug: alembic-dev-log-2026-08
tags: [alembic, network automation, newsletter]
summary: "0.9.0: a larger team, identity through uid, and an operating guide for agents.<br/>`cargo install alembic-cli`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/alembic
    - label: docs
      url: https://github.com/cyberwitchery/alembic/tree/main/docs
    - label: crates.io
      url: https://crates.io/crates/alembic-cli
---

third issue of the [alembic](https://github.com/cyberwitchery/alembic)
dev log. august brings one large release: **alembic 0.9.0**, released on
august 28.

## team

the largest change this month is organizational.

**[erik svedäng](https://www.eriksvedang.com)** will now be working on alembic
continuously, rather than contributing in separate stretches. that gives the
engine and commercial layer another sustained pair of hands. i’ve always thought
of alembic as a bit of a compiler, so who better to have onboard than the person
i’ve been co-maintaining [a compiler](https://github.com/carp-lang/Carp/) with
for the past 9 years?

we also onboarded **[alasdair wilkins](https://github.com/AlasdairWilkins)**.
he’ll be working on more of the commercial connector set.

**[piya gehi](https://orgnizedmess.net/)** continues her work on eve-ng. the
connector can now read a lab into alembic’s model, with interfaces referring to
their devices in the same uid space the planner uses.

## identity through uid

the main change in 0.9.0 is a simpler identity law. in a nutshell: **an object’s
identity is its uid**.

previously, a one-to-one `map` emit derived a new uid from the target type and
key. a map that renamed a key therefore turned one logical object into a delete
and a create. that was technically consistent with value-derived identity, but
wrong for the job the map was describing.

a one-to-one emit now keeps the source uid, including through `passthrough`.
changing a key plans as an update. a map that deliberately produces several
objects must assign their identities explicitly, and `uid: target` remains the
spell to derive one from the target type and key.

state follows the same rule. it is now scoped to one backend instance, and
`import` takes an object’s identity from state before considering its current
key. a rename in the backend therefore comes back as the same object. first-time
adoption is reported, ambiguous keys fail only when alembic actually needs to
match one, and moving a uid between types is shown as a `retype`.

inventories also gained an explicit `scope:` block. it defines which part of a
backend an inventory claims to describe, so `extra` and `--allow-delete` stay
inside that boundary. two inventories can share a backend without treating each
other’s objects as deletion candidates. no more cross-team whack-a-mole.

## alembic for agents

`0.9.0` ships an operational guide for coding agents.

the cli can reject an invalid command, but it cannot tell whether a valid one
matches the operator’s intent. an agent has to know that an absent attribute is
unmanaged rather than cleared, that changing a uid describes a different
object, and that `plan --report --provision` is not read-only.

the bundled `alembic` skill states those rules and carries worked workflows for
inspection, planning, and apply. its fixtures exercise the cases against a
file-backed adapter, so this is checked behaviour rather than a prompt that only
sounds plausible. `alembic skill list|show|install` writes the guide into an
agent’s skill directory without replacing a modified copy unless asked.

we live in a world where autonomous agents operate more and more of our tools, and
if we want any chance of success we should make sure they understand them.

## correctness notes

resumable apply now keeps an append-only journal through the delete phase and
records the backend id returned by each operation. a killed process resumes from
what reached the backend, including a partially completed set of deletes, and a
journal cannot be resumed against another backend instance.

the external-adapter boundary got stricter as well. responses are checked for
unknown fields, observed objects are validated against the requested schema,
and provisioning is refused when an adapter cannot preview it. netbox and
nautobot also converge declared validation rules and choices onto existing
custom fields instead of handling them only at creation.

finally, i restored the live netbox-and-infrahub end-to-end run before tagging
0.9.0. it caught two stale examples, one still using an interface-field alias
removed in 0.7.0 and one declaring a name netbox reserves. both were fixed for
the release. i can’t even remember why i ever turned it off, but i’m glad it’s
back.

next issue at the end of september.
