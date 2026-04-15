# log

the cyberwitchery blog engine. a small python script that turns markdown
posts into a static site and uploads it over webdav.

## post format

each post is a markdown file in `posts/` with yaml frontmatter:

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

optional frontmatter fields:

- `links?`: set to `true` to display a list of links
- `links`: a list of `{label, url}` objects rendered below the post

posts with a `date` in the future are excluded from the build until that
date arrives.

## publishing

```
python publish.py
```

this will:

1. read every post from `posts/`.
2. render html through the pystache templates in `templates/`.
3. generate an rss feed (`feed.rss`).
4. upload everything to the configured webdav endpoint.

webdav credentials and the remote path live in `config.py` (gitignored).
the file must define `opts` (a dict passed to `webdav3.client.Client`) and
`remote_root` (the remote directory path).

## dependencies

listed in `requirements.txt`:

- **pystache** — mustache templating
- **pypandoc** — markdown-to-html conversion (requires pandoc on `$PATH`)
- **pyyaml** — frontmatter parsing
- **webdavclient3** — webdav upload

install with:

```
pip install -r requirements.txt
```

## directory layout

```
posts/          markdown source files
templates/      pystache templates (index, post, rss feed)
publish.py      build-and-upload script
config.py       webdav credentials (gitignored)
out/            generated html + rss (gitignored)
```

<hr/>

have fun!
