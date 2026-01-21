---
title: "familiar: prompts as cli primitives"
date: 2026-01-21
slug: familiar
tags: [ai, agents, tooling, release]
summary: "compose and invoke agent prompts from reusable templates: conjurings + invocations. <br/>`pip install familiar`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/familiar
    - label: docs
      url: https://familiar.readthedocs.io/
    - label: pypi
      url: https://pypi.org/project/familiar-cli/
---

familiar is a tiny cli to automate tasks and bootstrap agents.

## why?

i had a list of prompts on my system that i kept pulling out. the rest of the
prompts lived somewhere in my claude history or was forever forgotten. i wanted a
central but simple way to orchestrate my tasks and help me set up new agent
definitions on the projects i work on and only slot in the arguments that i need
to change every time.

## what it is

new agents are **conjured** from composable templates, which will slot into an agent
prompt. tasks are **invoked**, with or without arguments.

the system ships with a few interesting conjuring and invocations you can **list**,
and you can override everything in your working directory via `.familiar/`, so you
and your team can work on your own conventions.

additionally, familiar ships with a simple **linter** that vets your invocation
format, and a **plugin system** that lets you define new agents and lint rules.
it’s simple enough to be easily understandable and extensible without hassle, and
powerful enough to support real workflows.

it’s new and in beta, but already useful if you have workflows you repeat and keep
misremembering the prompts of.

## quick start

```bash
pip install familiar-cli

# compose system rails (example: rust + security)
familiar conjure codex rust sec

# run a task prompt
familiar invoke codex code-review "the authentication module"

# see what's built in
familiar list
```
