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

## dependencies

install with:

```
pip install -r requirements.txt
```

<hr/>

have fun!
