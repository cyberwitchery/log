import argparse
import os
import re
import shutil
import sys

from email import utils
from datetime import date, datetime, time, timezone

import pystache
import pypandoc
import yaml


def upload_files():
    from webdav3.client import Client
    from webdav3.exceptions import ConnectionException, NoConnection, WebDavException

    from config import opts, remote_root

    c = Client(opts)
    failed = []
    for root_dir, _dirs, files in os.walk("out"):
        rel_dir = os.path.relpath(root_dir, "out")
        if rel_dir != ".":
            remote_dir = f"{remote_root}/{rel_dir}"
            try:
                if not c.check(remote_dir):
                    c.mkdir(remote_dir)
            except (ConnectionException, NoConnection) as e:
                print(
                    f"ERROR: connection lost creating {rel_dir}: {e}", file=sys.stderr
                )
                sys.exit(1)
            except WebDavException as e:
                print(
                    f"ERROR: failed to create remote dir {rel_dir}: {e}",
                    file=sys.stderr,
                )
                failed.append(rel_dir)
                continue
        for filename in files:
            rel_path = os.path.normpath(os.path.join(rel_dir, filename))
            local_path = os.path.join(root_dir, filename)
            remote_path = f"{remote_root}/{rel_path}"
            try:
                c.upload_sync(remote_path=remote_path, local_path=local_path)
            except (ConnectionException, NoConnection) as e:
                print(
                    f"ERROR: connection lost uploading {rel_path}: {e}", file=sys.stderr
                )
                sys.exit(1)
            except WebDavException as e:
                print(f"ERROR: failed to upload {rel_path}: {e}", file=sys.stderr)
                failed.append(rel_path)
    if failed:
        print(
            f"ERROR: {len(failed)} file(s) failed to upload: {', '.join(failed)}",
            file=sys.stderr,
        )
        sys.exit(1)


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


def render_sitemap(tpl, posts):
    with open("out/sitemap.xml", "w+", encoding="utf-8") as f:
        f.write(
            pystache.render(
                tpl,
                {
                    "today": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "posts": posts,
                },
            )
        )


def render_feed(tpl, posts):
    with open("out/feed.rss", "w+", encoding="utf-8") as f:
        f.write(
            pystache.render(
                tpl,
                {
                    "date": utils.format_datetime(datetime.now(timezone.utc)),
                    "posts": posts,
                },
            )
        )


def render_post(tpl, args):
    with open(f"out/{args['out_file']}", "w+", encoding="utf-8") as f:
        f.write(pystache.render(tpl, args))


def render_index(tpl, posts, alltags):
    with open("out/index.html", "w+", encoding="utf-8") as f:
        f.write(pystache.render(tpl, {"posts": posts, "alltags": alltags}))


def get_post(target):
    with open(f"posts/{target}", encoding="utf-8") as f:
        contents = f.read()

    try:
        args, content = split_frontmatter(contents)
    except yaml.YAMLError as e:
        print(
            f"WARNING: skipping {target}: frontmatter YAML parse error: {e}",
            file=sys.stderr,
        )
        return None

    if "date" not in args:
        print(
            f"WARNING: skipping {target}: missing required 'date' field in frontmatter",
            file=sys.stderr,
        )
        return None

    if isinstance(args["date"], str):
        try:
            args["date"] = date.fromisoformat(args["date"])
        except ValueError:
            print(
                f"WARNING: skipping {target}: invalid date format: {args['date']}",
                file=sys.stderr,
            )
            return None

    slug = args.get("slug", from_path(target))
    args["filename"] = target
    args["out_file"] = f"{slug}.html"
    args["date_iso"] = args["date"].strftime("%Y-%m-%d")
    args["date_and_time"] = utils.format_datetime(
        datetime.combine(args["date"], time(tzinfo=timezone.utc))
    )
    args["summary"] = pypandoc.convert_text(
        args.get("summary", ""), "html", format="md"
    )
    args["content"] = pypandoc.convert_text(content, "html", format="md")

    raw_tags = args.get("tags", [])
    args["data_tags"] = ",".join(raw_tags)
    if raw_tags:
        args["has_tags"] = True
        args["tags"] = [{"name": t} for t in raw_tags]

    return args


def build_alltags(posts):
    counts = {}
    for post in posts:
        for tag in post.get("tags", []):
            name = tag["name"]
            counts[name] = counts.get(name, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"name": name} for name, _ in ordered]


def copy_assets():
    if os.path.isdir("assets"):
        shutil.copytree("assets", "out/assets", dirs_exist_ok=True)


def get_posts():
    today = datetime.now(timezone.utc).date()
    posts = [get_post(f) for f in os.listdir("posts") if f.endswith(".md")]
    posts = [p for p in posts if p is not None and p["date"] <= today]
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


TEMPLATES = [
    "templates/index_layout.html",
    "templates/layout.html",
    "templates/feed_tpl.rss",
    "templates/sitemap_tpl.xml",
]


def main(dry_run=False):
    missing = [t for t in TEMPLATES if not os.path.isfile(t)]
    if missing:
        print(f"ERROR: missing template file(s): {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    os.makedirs("out", exist_ok=True)
    posts = get_posts()

    copy_assets()

    with open("templates/index_layout.html", encoding="utf-8") as f:
        tpl = f.read()

    render_index(tpl, posts, build_alltags(posts))

    with open("templates/layout.html", encoding="utf-8") as f:
        tpl = f.read()

    for post in posts:
        render_post(tpl, post)

    with open("templates/feed_tpl.rss", encoding="utf-8") as f:
        tpl = f.read()

    render_feed(tpl, posts)

    with open("templates/sitemap_tpl.xml", encoding="utf-8") as f:
        tpl = f.read()

    render_sitemap(tpl, posts)

    if dry_run:
        file_count = sum(len(files) for _, _, files in os.walk("out"))
        print(f"dry run: wrote {file_count} file(s) to out/, skipping upload")
        return

    upload_files()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="build and upload the cyberwitchery log"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build all files into out/ but do not upload",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
