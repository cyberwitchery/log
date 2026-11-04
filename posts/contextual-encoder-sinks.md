---
title: "contextual-encoder after done"
date: 2026-11-09
author: "Veit Heller"
slug: contextual-encoder-after-done
tags: [security, rust, tooling]
summary: "five releases and a bunch of breaking changes after we called it done.<br/>`cargo add contextual-encoder`"
"links?": true
links:
    - label: repo
      url: https://github.com/cyberwitchery/contextual-encoder
    - label: changelog
      url: https://github.com/cyberwitchery/contextual-encoder/blob/main/CHANGELOG.md
    - label: crates.io
      url: https://crates.io/crates/contextual-encoder/
---

in june i [introduced contextual-encoder](https://cyberwitchery.com/log/contextual-encoder.html)
and said i considered it done. no new contexts unless the need arises. and i
stayed true to that. still, since then it has had five more releases, 0.7.0 to
0.11.0, with a bunch of breaking changes between them. none of them added a context,
and yet they were all necessary.

the june post made the argument that you should encode output for where it goes
instead of scrubbing input. i still think that.

what the work since then made clear is how much “where it goes” matters. a
sink is just not a string with some special characters, and i can’t just
eyeball it and say “looks right”.

## context needs boundary

the simplest example was the [css url report](https://github.com/cyberwitchery/contextual-encoder/issues/49).
[`for_css_url`](https://docs.rs/contextual-encoder/latest/contextual_encoder/css/fn.for_css_url.html) left parentheses alone. inside an unquoted `url(...)`, an
attacker-controlled `)` closes the url token, and the rest of the input can
become a declaration. we had an encoder for the context, but its rules did
not enforce the right boundaries.

the more interesting failures were at the edges of encoded values. a css
hex escape can consume up to six hex digits. if the encoder ends its output
with `\3c` and the caller appends `a`, the parser reads `\3ca`, a different
character. the encoder now terminates that final escape with a separator
space. looking ahead inside the input was not enough, because the next
character could come from the template.

template literals had the same problem with `${`. we first escaped a trailing
`$`, so a `{` written after the value could not open an interpolation. that
still left the other edge: trusted text ending in `$`, followed by an
untrusted value starting with `{7*6}`.

```javascript
// before: trusted "total: $" followed by encoded "{7*6}"
`total: ${7*6}` // evaluates to "total: 42"

// after: the leading brace is escaped
`total: $\x7b7*6}` // evaluates to "total: ${7*6}"
```

that [fix](https://github.com/cyberwitchery/contextual-encoder/pull/79), and
the latest xml comment and cdata fixes, are in the very latest release.

i think this is the useful class of bugs to remember: the encoder only sees
its input, but its output participates in a larger grammar. testing two
encoded writes next to each other also misses cases where one side is raw
trusted template text. nothing is ever as easy as it seems.

## sometimes there is more than one parser

inside a `<script>` element, the html tokenizer gets to the text before the
javascript engine does. escaping `/` stopped a literal `</script>`, but an
input containing `<!--<script>` could still put the html tokenizer into its
double-escaped script state. the template’s real closing `</script>` then
failed to close the element. the script encoders now escape `<` too.

xhtml adds another variation: its xml parser resolves character references
before javascript sees them. a literal `&#96;` in untrusted input can arrive
at the javascript parser as a backtick. [`for_js_template`](https://docs.rs/contextual-encoder/latest/contextual_encoder/javascript/fn.for_js_template.html) therefore has to
escape `&` as well.

not every failure was an injection. xml 1.1 normalizes raw NEL and line
separator characters to line feeds, so preserving them requires character
references. [`for_rust_char`](https://docs.rs/contextual-encoder/latest/contextual_encoder/rust/fn.for_rust_char.html) could escape every character correctly and still
produce an invalid literal from `ab`[^1]. these are different failures, but
they all require checking what the consumer actually accepts and reads.

## as ever: fuzz it

this all made me break down and write a differential fuzzing harness in a
separate crate. it generates inputs, encodes them, inserts the output into
a small document or literal, and runs an independent parser over it.

the checks depend on the sink. `html5ever` checks for unexpected elements
and attributes. `cssparser` checks that quoted css values remain one string
token. `quick-xml` reads xml content, attributes, comments and cdata.
`serde_json` parses json strings, and the boa javascript engine evaluates
string and template literals.

the inputs combine a fixed regression corpus, fragments such as `</script>`,
`${` and `]]>`, and random unicode scalar values. fixed seeds make a failure
reproducible. this is a small deterministic fuzzing run, with parser results
as the oracle. comparing bytes against another encoder is useful for
conformance, but two encoders can agree on an output that the sink reads
incorrectly.

there is a limitation here i want to call out, though: the current harness
mostly wraps a value directly in its delimiters. it does not yet vary trusted
text on both sides, and its parser coverage does not span every encoder. the
boundary sweeps recorded in the recent fixes utilize exactly that surrounding
text.

so the property i want to check is that the whole composed sink keeps its
structure and reads back the intended value. the fuzzing is useful when the
oracle and the surrounding template fulfill that contract.

the harness stays outside the library’s workspace and has its own lockfile.
its parser dependencies can be large and contain unsafe code without entering
the published crate’s dependency graph or its unsafe budget. it’ll not be
published on crates.io, because why would i do that?

not every useful crate needs to be published.

## takeaway

the fixes themselves were largely written by our agents, and two of them
started with outside reports from [hey-jj](https://github.com/hey-jj)
(thanks, kind stranger!). i didn’t find them by staring at the code and
thinking real hard.

as is often the case, a bit of fuzzing replaces a lot of thinking, and does a better job.
the bitter lesson of application security, i suppose.

it’s still done, in the june-announcement sense. the list of contexts isn’t
growing. we’re just making the existing invariants reliable.

[^1]: also [reported by hey-jj](https://github.com/cyberwitchery/contextual-encoder/issues/63).
[`for_rust_char_checked`](https://docs.rs/contextual-encoder/latest/contextual_encoder/rust/fn.for_rust_char_checked.html) now returns `None` unless the input is exactly one
unicode scalar value. the original function documents that precondition.
