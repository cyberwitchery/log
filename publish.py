import os
import re

from email import utils
from datetime import datetime

import pystache
import pypandoc
import yaml

from webdav3.client import Client

from config import opts, remote_root


c = Client(opts)

def upload_files():
    for filename in os.listdir("out"):
        remote_path = f"{remote_root}/{filename}"
        c.upload_sync(remote_path=remote_path, local_path=f"out/{filename}")


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
    body = md[m.end():]
    return meta, body


def render_feed(tpl, posts):
    with open("out/feed.rss", "w+") as f:
        f.write(pystache.render(tpl, {"date": utils.format_datetime(datetime.now()), "posts": posts}))


def render_post(tpl, args):
    with open(f"out/{args['out_file']}", "w+") as f:
        f.write(pystache.render(tpl, args))


def render_index(tpl, posts):
    with open("out/index.html", "w+") as f:
        f.write(pystache.render(tpl, {"posts": posts}))


def get_post(target):
    with open(f"posts/{target}") as f:
        contents = f.read()

    args, content = split_frontmatter(contents)
    args["filename"] = target
    args["out_file"] = out_file(target)
    args["date_and_time"] = utils.format_datetime(datetime.combine(args["date"], datetime.min.time()))
    args["summary"] = pypandoc.convert_text(args.get("summary", ""), "html", format="md")
    args["content"] = pypandoc.convert_text(content, "html", format="md")

    return args


def get_posts():
    posts = [get_post(f) for f in os.listdir("posts")]
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def main():
    os.makedirs("out", exist_ok=True)
    posts = get_posts()

    with open('templates/index_layout.html') as f:
        tpl = f.read()

    render_index(tpl, posts)

    with open('templates/layout.html') as f:
        tpl = f.read()

    for post in posts:
        render_post(tpl, post)

    with open('templates/feed_tpl.rss') as f:
        tpl = f.read()

    render_feed(tpl, posts)

    upload_files()


if __name__ == '__main__':
    main()
