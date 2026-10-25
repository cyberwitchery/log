---
title: "all the way down: metacarp, a self-hosting compiler for carp"
date: 2026-10-27
author: "Veit Heller, Erik Svedäng"
slug: cw003-all-the-way-down
tags: [papers, compilers, carp]
summary: "the third note in the cyberwitchery paper series. a compiler for carp, written in carp, that builds itself and runs as a library behind editors and notebooks.<br/>`CW:003 · experience report · v1.0`"
"links?": true
links:
    - label: paper (pdf)
      url: https://cyberwitchery.com/papers/cw003-all-the-way-down.pdf
    - label: metacarp
      url: https://github.com/cyberwitchery/metacarp
    - label: the series
      url: https://cyberwitchery.com/papers.html
---

the third note in the paper series is out:
[`CW:003`, all the way down](https://cyberwitchery.com/papers/cw003-all-the-way-down.pdf).
the series is indexed at
[cyberwitchery.com/papers](https://cyberwitchery.com/papers.html).

this is the first paper with two authors.

## why?

this one is closer to home than the last two. erik created
[carp](https://github.com/carp-lang/Carp), veit has co-maintained it since
2017, and [metacarp](https://github.com/cyberwitchery/metacarp) is a compiler
for it, written in carp, when the work was revitalized in 2026.

the reference compiler is written in haskell, which has a garbage collector and
a whole bunch of fancy affordances. carp doesn’t, so writing its compiler in
carp means everything needs an owner and a lifetime, and a lot of machinery
needs to exist for the thing to work. we think that makes a compiler a good
test of a language, because it fails exactly where the language has blind
spots.

we also, along the way, incorporated a lot of learnings, and metacarp can do a
lot of things the reference cannot do, most importantly be used as a library
with the individual passes activating on demand.

## the paper

metacarp compiles its own source, and successive generations emit
byte-identical c. this means the compiler bootstraps, and it’s quite fast as
well.

most of the report is about what we built to get there. a parser, a bytecode
vm for macros, machinery to generate code, specialization passes, ownership,
type unification, and two backends (c and llvm).

the second half talks about another use of the compiler: as a library and for
long-lived sessions. a session keeps a baseline checked between requests,
accepts transactional edits, and answers queries for editors and notebooks.
the llvm backend keeps compiled definitions around between cells.

on an m1 max, metacarp emits its own source in a median 8.5 seconds, against
296 seconds for the reference compiler. warm inference on a small cell takes
31 milliseconds, warm native compilation and execution 40ms. the programs it
generates are not faster, though. metacarp doesn’t optimize anything (yet).

but we are not done.

as before: not peer reviewed. read it with that in mind, and
[argue with us](mailto:contact@cyberwitchery.com?subject=papers) if you think
it’s wrong.
