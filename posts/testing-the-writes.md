---
title: "how we test the writes: fault injection and resumable apply"
date: 2026-07-23
slug: testing-the-writes
tags: [alembic, network automation, tooling]
summary: "apply is the only step that writes. half-finished apply stays safe with a journal that resumes, writes safe to repeat, and an adapter whose only job is to fail.<br/>`cargo install alembic-cli`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/alembic
    - label: docs
      url: https://github.com/cyberwitchery/alembic/tree/main/docs
    - label: crates.io
      url: https://crates.io/crates/alembic-cli
---

if you work with alembic, you run the same five-step loop every time (`validate` →
`import` → `map` → `plan` → `apply`), and only the last step writes. everything
before it is read-only. `apply` takes a plan you have already seen and pushes it
to a real backend, in order. this it the only guardrail on safety and it puts all
of the weight on one step. so the question worth asking is: what happens when
that one step dies halfway through?

a crash, a dropped connection, a rate-limit at op 400 of 900, and it dies. you can’t
let that leave the backend half-written, and you can’t let the next run pile up
duplicates of what already landed. this post is about the machinery that makes a
partial write recoverable, and the method we use to trust it: breaking it on
purpose.

## why resume is even possible

resume is only well-defined if the plan is deterministic and ordered. alembic’s
plans are both. a plan is a function of the desired state and the observed
backend snapshot, so the same inputs produce the same ops every time. and those
ops are put through a stable topological sort[^1], so a referenced object is
always created before the thing that points at it, and deletes run in reverse.

that ordering both lets apply satisfy references as it goes, and it also
makes any stopping point a well-defined position in a fixed sequence rather than
a guess.

## the journal

on top of that, apply keeps a journal: a small on-disk record, under
`.alembic/`, of which ops have already been applied. each entry is the op’s
uid, its type, a hash of the op itself, whether it’s done, and the backend id it
produced. it’s written the careful way, meaning to a temp file, fsync’d, atomically
renamed, and then the directory fsync’d, so the journal can survive the same
crash it exists to protect against. this might seem overkill, but the only
reason it’s there is to provide a faithful record of what happened, so we might
as well do it right.

on the next run, apply reloads the journal, checks that its op hashes match the
current plan exactly (a plan that changed is not a plan you can resume, so it
errors out rather than guess), and skips the creates and updates it already
finished, keyed by `(uid, type, hash)`. there’s no flag to set: a half-applied
plan just picks up where it stopped when you run it again[^2]. this is
[erik svedäng](https://www.eriksvedang.com)’s work, and i’m extreemely grateful
for it. i tried breaking it with him in a few sessions, and we only merged it
when we were truly happy with it.

## idempotency, because resume isn’t exactly-once

a journal that skips finished ops gets you most of the way, but not all of it.
an op can die in the window between writing to the backend and recording itself
as done, so resume has to assume it might re-issue that op. deletes aren’t
journaled at all, so they run again on a resumed apply. both mean apply can’t
count on doing each write exactly once, sine it has to be safe to repeat.

so every adapter is idempotent by construction. a create that comes back with an
“already exists” conflict recovers by looking the object up by key and treating
it as done, rather than failing. a delete whose target is already gone is a
no-op, not an error. netbox and nautobot were already built this way. this month
infrahub and generic were hardened to match, each logging a warning on the
tolerated case so the recovery path stays visible instead of silent.

## proving it: break it on purpose

erik wasn’t done, though. he had another idea that he just pitched and
implemented out of nowhere, and i was delighted to see it.

you can’t trust resume unless you can crash on purpose, at a spot you choose. so
the recovery path is tested with fault injection rather than hope. `erratic` is
an internal adapter whose entire job is to fail: point it at an op index and it
errors right before that op, or hand it a probability and it fails a fraction of
ops at random. it’s the backend you run apply against when you want to watch a
write die mid-plan. it’s basically an adapter specifically built for chaos
engineering.

the check itself lives in the open engine: drive a plan until it dies at a
chosen op, resume, and assert two things: the resumed run applies only the ops
the first hadn’t finished, and the backend ends in exactly the planned state.
one case kills apply after an error and confirms the second run applies just the
remainder, another shuffles the op order and confirms resume still lines up.
break it, resume it, check the backend landed where the plan expected.

it lets us sleep at night, and i’m all for things that let me sleep a little.

## the wider net

fault injection covers one op dying. the subtler failure mode is a change
somewhere upstream quietly altering what apply would write in the first place.

that one is caught by a different test. we drive the fabric end-to-end, which
boots a real netbox, runs `seed → import → map → emit`, and diffs every generated
artifact against a committed golden baseline.

it lets us stay faithful to our promise of one model and many outputs. we’ll give that
fabric its own post in a later installment. here it’s enough to say it’s the regression
net behind “one model feeds every tool”, and we end up catching errors in virtualized
devices and their observability layer if it ever stops working.

## the cost of the claim

i once promised a client that nothing changes by surprise, which is a simple
enough statement. underneath it are three unglamorous things: a journal that survives
the crash it’s meant to protect against, writes idempotent enough that repeating one is a
no-op instead of a mess, and an adapter whose only job is to fail on command so the
recovery path gets exercised instead of assumed.

to put it pithily: boringness requires real engineering.

[^1]: for the curios: we use kahn’s algorithm with a deterministic tie-breaker on
type, kind, and key.

[^2]: resume here is a property of the in-tree adapters (netbox, nautobot,
infrahub, generic). an external adapter receives its whole op batch in a single
call and is responsible for its own recovery.
