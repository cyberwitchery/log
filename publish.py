import os
import re
import sys

from email import utils
from datetime import datetime

import pystache
import pypandoc
import yaml

from webdav3.client import Client
from webdav3.exceptions import ConnectionException, NoConnection, WebDavException

from config import opts, remote_root


c = Client(opts)


def upload_files():
    failed = []
    for filename in os.listdir("out"):
        remote_path = f"{remote_root}/{filename}"
        try:
            c.upload_sync(remote_path=remote_path, local_path=f"out/{filename}")
        except (ConnectionException, NoConnection) as e:
            print(f"ERROR: connection lost uploading {filename}: {e}", file=sys.stderr)
            sys.exit(1)
        except WebDavException as e:
            print(f"ERROR: failed to upload {filename}: {e}", file=sys.stderr)
            failed.append(filename)
    if failed:
        print(
            f"ERROR: {len(failed)} file(s) failed to upload: {', '.join(failed)}",
            file=sys.stderr,
        )
        sys.exit(1)


def tag_slug(tag):
    return re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-")


def from_path(f):
    return os.path.basename(f)[:-3]


def out_file(f):
    return "{}.html".format(from_path(f))


FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def split_frontmatter(md):
    m = FM_RE.match(md)
    if not m:
        return {}, md
    meta_raw = m.group(1)
    meta = yaml.safe_load(meta_raw) or {}
    body = md[m.end() :]
    return meta, body


def render_feed(tpl, posts):
    with open("out/feed.rss", "w+") as f:
        f.write(
            pystache.render(
                tpl, {"date": utils.format_datetime(datetime.now()), "posts": posts}
            )
        )


def render_post(tpl, args):
    with open(f"out/{args['out_file']}", "w+") as f:
        f.write(pystache.render(tpl, args))


def render_index(tpl, posts):
    with open("out/index.html", "w+") as f:
        f.write(pystache.render(tpl, {"posts": posts}))


def render_tag_pages(tpl, posts):
    tags = {}
    for post in posts:
        for t in post.get("tags", []):
            tags.setdefault(t["tag"], []).append(post)
    for tag, tag_posts in tags.items():
        filename = f"tag-{tag_slug(tag)}.html"
        with open(f"out/{filename}", "w+") as f:
            f.write(pystache.render(tpl, {"tag": tag, "posts": tag_posts}))


def get_post(target):
    with open(f"posts/{target}") as f:
        contents = f.read()

    args, content = split_frontmatter(contents)

    if "date" not in args:
        print(
            f"WARNING: skipping {target}: missing required 'date' field in frontmatter",
            file=sys.stderr,
        )
        return None

    args["filename"] = target
    args["out_file"] = out_file(target)
    args["date_and_time"] = utils.format_datetime(
        datetime.combine(args["date"], datetime.min.time())
    )
    args["summary"] = pypandoc.convert_text(
        args.get("summary", ""), "html", format="md"
    )
    args["content"] = pypandoc.convert_text(content, "html", format="md")

    raw_tags = args.get("tags", [])
    if raw_tags:
        args["tags"] = [
            {"tag": t, "tag_file": f"tag-{tag_slug(t)}.html"} for t in raw_tags
        ]
        args["has_tags"] = True

    return args


def get_posts():
    today = datetime.now().date()
    posts = [get_post(f) for f in os.listdir("posts")]
    posts = [p for p in posts if p is not None and p["date"] <= today]
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


TEMPLATES = [
    "templates/index_layout.html",
    "templates/layout.html",
    "templates/tag_layout.html",
    "templates/feed_tpl.rss",
]


def main():
    missing = [t for t in TEMPLATES if not os.path.isfile(t)]
    if missing:
        print(f"ERROR: missing template file(s): {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    os.makedirs("out", exist_ok=True)
    posts = get_posts()

    with open("templates/index_layout.html") as f:
        tpl = f.read()

    render_index(tpl, posts)

    with open("templates/layout.html") as f:
        tpl = f.read()

    for post in posts:
        render_post(tpl, post)

    with open("templates/tag_layout.html") as f:
        tpl = f.read()

    render_tag_pages(tpl, posts)

    with open("templates/feed_tpl.rss") as f:
        tpl = f.read()

    render_feed(tpl, posts)

    upload_files()


if __name__ == "__main__":
    main()
