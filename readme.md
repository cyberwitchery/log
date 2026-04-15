# log

The cyberwitchery blog engine. A small Python script that turns markdown
posts into a static site and uploads it over WebDAV.

## Post format

Each post is a markdown file in `posts/` with YAML frontmatter:

```markdown
---
title: "my post title"
date: 2026-01-15
slug: my-post
tags: [topic-a, topic-b]
summary: "one-line summary shown on the index page"
---

Post body in markdown.
```

Optional frontmatter fields:

- `links?`: set to `true` to display a list of links
- `links`: a list of `{label, url}` objects rendered below the post

Posts with a `date` in the future are excluded from the build until that
date arrives.

## Publishing

```
python publish.py
```

This will:

1. Read every post from `posts/`.
2. Render HTML through the pystache templates in `templates/`.
3. Generate an RSS feed (`feed.rss`).
4. Upload everything to the configured WebDAV endpoint.

WebDAV credentials and the remote path live in `config.py` (gitignored).
The file must define `opts` (a dict passed to `webdav3.client.Client`) and
`remote_root` (the remote directory path).

## Dependencies

Listed in `requirements.txt`:

- **pystache** — Mustache templating
- **pypandoc** — markdown-to-HTML conversion (requires pandoc on `$PATH`)
- **pyyaml** — frontmatter parsing
- **webdavclient3** — WebDAV upload

Install with:

```
pip install -r requirements.txt
```

## Directory layout

```
posts/          markdown source files
templates/      pystache templates (index, post, RSS feed)
publish.py      build-and-upload script
config.py       WebDAV credentials (gitignored)
out/            generated HTML + RSS (gitignored)
```
