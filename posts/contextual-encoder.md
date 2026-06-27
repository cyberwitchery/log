---
title: "contextual-encoder: output encoding for xss defense"
date: 2026-06-19
slug: contextual-encoder
tags: [security, rust, tooling, release]
summary: "encode untrusted strings for the context they land in<br/>`cargo add contextual-encoder`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/contextual-encoder
    - label: docs
      url: https://docs.rs/contextual-encoder/
    - label: crates.io
      url: https://crates.io/crates/contextual-encoder/
---

`contextual-encoder` is a zero-dependency rust crate that encodes untrusted
strings for safe embedding in a specific output context. it covers the web
sinks (html, javascript, css, uri, xml), json, and two source-literal contexts
(rust and sql).

the web encoders are modeled on the
[owasp java encoder](https://owasp.org/owasp-java-encoder/), which is the thing
i’d reach for in the jvm world and the reason i trust the approach at all. the
owasp project has spent years getting the per-context encoding rules and the
security caveats right, and i didn’t want to relearn those lessons from scratch
in rust, so the html, javascript, css, uri, and xml encoders follow its rules
deliberately closely[^1]. the json and source-literal encoders are additions
the java library doesn’t have.

## why?

the right way to stop xss isn’t to scrub input, it’s to encode output for the
exact place it’s going. the catch is that “the exact place” matters a lot. a
string that’s safe inside an html attribute is not safe inside a `<script>`
block, and neither is safe inside a `url()` in css. encode for the wrong
context and you either over-encode (garbled output) or under-encode (a hole).

so the whole premise is one function per context, each encoding only the
characters that context actually requires. you pick the sink, the crate
encodes for it.

## quick start

```rust
use contextual_encoder::{for_html, for_javascript, for_css_string, for_uri_component};

let input = "<script>alert('xss')</script>";

for_html(input);
// => &lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;

for_javascript(input); 
// hex-encodes quotes, escapes / so </script> can't close the block

for_css_string(input);
// \3c style hex escapes

for_uri_component(input);
// RFC 3986 percent-encoding
```

every `for_*` function has a `write_*` counterpart that writes into any
`std::fmt::Write`, plus a `display_*` wrapper that returns a zero-allocation
`Display` type so you can drop it straight into a `format!` without an
intermediate `String`.

## what it covers

the bulk of it mirrors where untrusted data lands in web output: html (text
content, quoted attributes, unquoted attributes), xml 1.0 and 1.1, cdata and
xml comments, the four javascript contexts, es6 template literals, css strings
and `url()` values, and uri components and paths. each of those is a distinct
encoding, and the crate gives each its own function rather than one fuzzy
“escape” call.

then there are the non-web contexts: a json string encoder (distinct from the
javascript ones, with its own breakout rules), and encoders for embedding
untrusted strings as rust and sql literals. those are outside the owasp
encoder’s remit; i added them for the cases where i’m generating code or
queries rather than serving a page.

## what it deliberately won’t do

i think the more important half of a tool like this is what it refuses to
pretend it can do. encoding is not sanitizing: `for_html` makes `<script>`
display safely, it does not remove it. it’s also not validation. tag names,
attribute names, event-handler names, and url schemes have to be checked
against a whitelist separately, because no amount of encoding makes an
arbitrary one of those safe.

so a few contexts are intentionally unsupported and documented as such: raw
tag and attribute names, raw javascript expressions, css selectors and
properties, html comments, and full untrusted urls. `for_uri_component`
encodes a component, not a whole url, on purpose.

## design choices

a few things that matter more than they look:

- **only the necessary characters.** the conservative `for_html` is the safe
  default, but the narrower encoders (`for_html_content`, `for_html_attribute`)
  exist so you don’t pay to encode quotes in a context that doesn’t need it.
- **one shared engine.** every encoder runs through a single loop that writes
  safe runs verbatim and only diverts on characters a per-context predicate
  flags, with one character of lookahead for escapes that need it (css hex,
  for instance). adding a context is a predicate plus a writer, not a new
  scanner.
- **`#![forbid(unsafe_code)]` and zero dependencies.** a security primitive
  shouldn’t drag in a supply chain or its own memory-safety caveats.

the docs also carry the sharp edges over from the owasp encoder: the grave
accent in unquoted attributes on old internet explorer, and why string-literal
js encoders don’t cover template literals (use `for_js_template`, or encode
into a variable first).

## relationship to the owasp java encoder

the web encoders (html, javascript, css, uri, xml) match the java encoder’s
rules closely: the same html escape choices, the four javascript contexts, the
css hex-escape format down to the trailing-space separator, percent-encoding of
utf-8 bytes for uris, and the same documented caveats. if you know the java
library, this should feel familiar.

there are a few intentional deviations, mostly because rust isn’t java. java’s
`char[]` can hold lone surrogates, which the java encoder defends against; a
rust `&str` is guaranteed valid utf-8, so that whole class of input can’t
occur and supplementary-plane characters just pass through. `for_html` also
uses the numeric `&#34;`/`&#39;` forms over `&quot;` because they’re shorter
and equally valid.

## what’s next

initially, i wanted to expand the contexts. after all, i have an engine that
can run a variety of different rulesets, right? but then i realized that if i
want to stay confident in the library, i need to maintain a small surface. so
as of now, i consider this library “done” in terms of features. i still maintain
it, but i will not add any more contexts unless the need arises.

[^1]: it’s an independent crate, not affiliated with, endorsed by, or
maintained by the owasp foundation.
