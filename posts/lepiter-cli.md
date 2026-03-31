---
title: "lepiter-cli: a terminal editor for lepiter knowledge bases"
date: 2026-03-23
slug: lepiter-cli
tags: [tooling, release]
summary: "browse, search, and edit lepiter knowledge bases from your terminal<br/>`cargo install lepiter-cli`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/lepiter-cli
    - label: docs
      url: https://docs.rs/lepiter-core/
    - label: crates.io
      url: https://crates.io/crates/lepiter-cli/
---

[lepiter](https://lepiter.io/) is the notebook and knowledge base system behind
[glamorous toolkit](https://gtoolkit.com/). it stores pages as json files on
disk—which means you can read them without the gt environment. `lepiter-cli` does
exactly that: a terminal tool for browsing, searching, and editing lepiter
knowledge bases.

## quick start

```bash
# browse interactively
lepiter-cli tui ./my-knowledge-base

# list all pages
lepiter-cli list ./my-knowledge-base

# search
lepiter-cli search "pharo" ./my-knowledge-base --full-text

# render a page to stdout
lepiter-cli show "Page Title" ./my-knowledge-base
```

the tui gives you a searchable page list, full-screen page reading with
markdown-like rendering, and link navigation. `tab` cycles through links on a
page, `enter` follows them, `h` goes back.

## editing

press `e` in page view to enter the editor. it works at the snippet level—text
and code snippets are editable, everything else stays read-only. changes are
auto-saved after a short idle period and written back to the page json file.
`ctrl+u` undoes, `tab` moves between snippets.

## plugins

lepiter's schema has many snippet types, and new ones appear over time.
`lepiter-cli` handles unknown types via external plugins: long-lived processes
that receive snippet json over stdin and return rendered lines over stdout.

```json
{
  "plugins": [
    { "name": "wardley", "types": ["wardleyMap"] }
  ]
}
```

the plugin binary is resolved from `PATH` by convention
(`lepiter-plugin-<name>`), and `lepiter-core` exports a small sdk with a
`lepiter_plugin_main!` macro to cut the boilerplate. render output is cached
by snippet hash.

## structure

two crates:

- `lepiter-core`: parser, metadata index, plugin sdk, and plain text renderer.
  lazy loading—metadata is indexed on open, full pages parsed on demand.
- `lepiter-cli` (`lepiter-tui/`): the tui, editor, and all cli subcommands.

## resilience

lepiter's schema evolves. `lepiter-core` handles unknown snippet types by
preserving them as `Node::Unknown` with their raw json, so new snippet types
don't crash the tool—they just render as a fallback, or get routed to a
plugin if one is configured[^1]. non-fatal parse issues are collected
separately and don't abort indexing.

[^1]: the `probe` example in `lepiter-core` is useful for inspecting what
snippet types appear in a corpus and whether any are hitting the unknown path.
