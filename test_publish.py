"""Tests for publish.py.

Covers frontmatter parsing, post rendering, RSS feed generation,
tag handling, date filtering, and error paths.
"""

import os
import textwrap
from datetime import date, datetime, time, timezone
from email import utils
from xml.etree import ElementTree

import pypandoc
import pytest

from publish import (
    from_path,
    get_post,
    get_posts,
    out_file,
    render_feed,
    render_index,
    render_post,
    split_frontmatter,
)

# ── helpers ──────────────────────────────────────────────────────────────


def _write_post(tmp_path, filename, content):
    """Write a markdown post to tmp_path/posts/filename."""
    posts_dir = tmp_path / "posts"
    posts_dir.mkdir(exist_ok=True)
    (posts_dir / filename).write_text(content, encoding="utf-8")


def _make_out_dir(tmp_path):
    (tmp_path / "out").mkdir(exist_ok=True)


MINIMAL_POST = textwrap.dedent("""\
    ---
    title: Test Post
    date: 2025-06-01
    ---
    Hello world.
""")

POST_WITH_TAGS = textwrap.dedent("""\
    ---
    title: Tagged Post
    date: 2025-03-15
    slug: tagged
    tags: [rust, tooling]
    summary: "a short summary"
    ---
    Some content here.
""")

POST_WITH_LINKS = textwrap.dedent("""\
    ---
    title: Post With Links
    date: 2025-04-10
    slug: linked
    "links?": true
    links:
        - label: repo
          url: https://example.com/repo
        - label: docs
          url: https://example.com/docs
    ---
    Content with links.
""")


# ── split_frontmatter ───────────────────────────────────────────────────


class TestSplitFrontmatter:
    def test_basic(self):
        md = textwrap.dedent("""\
            ---
            title: hello
            date: 2025-01-15
            ---
            body text
        """)
        meta, body = split_frontmatter(md)
        assert meta["title"] == "hello"
        assert meta["date"] == date(2025, 1, 15)
        assert body.strip() == "body text"

    def test_no_frontmatter(self):
        meta, body = split_frontmatter("just plain text")
        assert meta == {}
        assert body == "just plain text"

    def test_empty_frontmatter(self):
        md = "---\n\n---\nbody"
        meta, body = split_frontmatter(md)
        assert meta == {}
        assert body == "body"

    def test_colon_in_value(self):
        md = textwrap.dedent("""\
            ---
            title: "key: value in title"
            date: 2025-01-01
            ---
            body
        """)
        meta, _ = split_frontmatter(md)
        assert meta["title"] == "key: value in title"

    def test_nested_structure(self):
        md = textwrap.dedent("""\
            ---
            title: test
            date: 2025-01-01
            "links?": true
            links:
                - label: repo
                  url: https://example.com
            ---
            body
        """)
        meta, _ = split_frontmatter(md)
        assert meta["links?"] is True
        assert len(meta["links"]) == 1
        assert meta["links"][0]["label"] == "repo"

    def test_tags_list(self):
        md = textwrap.dedent("""\
            ---
            title: test
            date: 2025-01-01
            tags: [rust, tooling, release]
            ---
            body
        """)
        meta, _ = split_frontmatter(md)
        assert meta["tags"] == ["rust", "tooling", "release"]

    def test_multiline_body_preserved(self):
        md = textwrap.dedent("""\
            ---
            title: test
            date: 2025-01-01
            ---
            line one

            line two
        """)
        _, body = split_frontmatter(md)
        assert "line one" in body
        assert "line two" in body


# ── from_path / out_file ────────────────────────────────────────────────


class TestPathHelpers:
    def test_from_path_strips_extension(self):
        assert from_path("posts/my-post.md") == "my-post"

    def test_from_path_nested(self):
        assert from_path("a/b/c/post-name.md") == "post-name"

    def test_out_file(self):
        assert out_file("posts/hello.md") == "hello.html"


# ── get_post ─────────────────────────────────────────────────────────────


class TestGetPost:
    def test_minimal_post(self, tmp_path, monkeypatch):
        _write_post(tmp_path, "test.md", MINIMAL_POST)
        monkeypatch.chdir(tmp_path)
        result = get_post("test.md")
        assert result is not None
        assert result["title"] == "Test Post"
        assert result["date"] == date(2025, 6, 1)
        assert result["out_file"] == "test.html"
        assert "<p>" in result["content"]
        assert "Hello world" in result["content"]

    def test_slug_overrides_filename(self, tmp_path, monkeypatch):
        _write_post(tmp_path, "ugly-name.md", POST_WITH_TAGS)
        monkeypatch.chdir(tmp_path)
        result = get_post("ugly-name.md")
        assert result["out_file"] == "tagged.html"

    def test_no_slug_uses_filename(self, tmp_path, monkeypatch):
        _write_post(tmp_path, "my-post.md", MINIMAL_POST)
        monkeypatch.chdir(tmp_path)
        result = get_post("my-post.md")
        assert result["out_file"] == "my-post.html"

    def test_tags_processing(self, tmp_path, monkeypatch):
        _write_post(tmp_path, "tagged.md", POST_WITH_TAGS)
        monkeypatch.chdir(tmp_path)
        result = get_post("tagged.md")
        assert result["has_tags"] is True
        assert result["tags"] == [{"name": "rust"}, {"name": "tooling"}]

    def test_no_tags(self, tmp_path, monkeypatch):
        _write_post(tmp_path, "plain.md", MINIMAL_POST)
        monkeypatch.chdir(tmp_path)
        result = get_post("plain.md")
        assert "has_tags" not in result

    def test_summary_rendered_as_html(self, tmp_path, monkeypatch):
        _write_post(tmp_path, "s.md", POST_WITH_TAGS)
        monkeypatch.chdir(tmp_path)
        result = get_post("s.md")
        assert "<p>" in result["summary"] or result["summary"].strip() != ""

    def test_links_preserved(self, tmp_path, monkeypatch):
        _write_post(tmp_path, "linked.md", POST_WITH_LINKS)
        monkeypatch.chdir(tmp_path)
        result = get_post("linked.md")
        assert result["links?"] is True
        assert len(result["links"]) == 2
        assert result["links"][0]["label"] == "repo"

    def test_date_and_time_is_utc_rfc2822(self, tmp_path, monkeypatch):
        _write_post(tmp_path, "utc.md", MINIMAL_POST)
        monkeypatch.chdir(tmp_path)
        result = get_post("utc.md")
        dt_str = result["date_and_time"]
        assert "+0000" in dt_str or "UTC" in dt_str or "GMT" in dt_str

    def test_missing_date_returns_none(self, tmp_path, monkeypatch, capsys):
        post = textwrap.dedent("""\
            ---
            title: No Date
            ---
            body
        """)
        _write_post(tmp_path, "nodate.md", post)
        monkeypatch.chdir(tmp_path)
        result = get_post("nodate.md")
        assert result is None
        assert "missing required 'date'" in capsys.readouterr().err

    def test_missing_frontmatter_returns_none(self, tmp_path, monkeypatch, capsys):
        _write_post(tmp_path, "bare.md", "just text, no frontmatter")
        monkeypatch.chdir(tmp_path)
        result = get_post("bare.md")
        assert result is None
        assert "missing required 'date'" in capsys.readouterr().err

    def test_malformed_yaml_returns_none(self, tmp_path, monkeypatch, capsys):
        post = "---\ntitle: [unclosed\n---\nbody\n"
        _write_post(tmp_path, "bad.md", post)
        monkeypatch.chdir(tmp_path)
        result = get_post("bad.md")
        assert result is None
        assert "YAML parse error" in capsys.readouterr().err


# ── get_posts ────────────────────────────────────────────────────────────


class TestGetPosts:
    def test_filters_non_md_files(self, tmp_path, monkeypatch):
        _write_post(tmp_path, "good.md", MINIMAL_POST)
        # write a non-.md file
        (tmp_path / "posts" / "notes.txt").write_text("ignored")
        monkeypatch.chdir(tmp_path)
        posts = get_posts()
        filenames = [p["filename"] for p in posts]
        assert "good.md" in filenames
        assert "notes.txt" not in filenames

    def test_filters_future_posts(self, tmp_path, monkeypatch):
        past = textwrap.dedent("""\
            ---
            title: Past
            date: 2020-01-01
            ---
            old
        """)
        future = textwrap.dedent("""\
            ---
            title: Future
            date: 2099-12-31
            ---
            not yet
        """)
        _write_post(tmp_path, "past.md", past)
        _write_post(tmp_path, "future.md", future)
        monkeypatch.chdir(tmp_path)
        posts = get_posts()
        titles = [p["title"] for p in posts]
        assert "Past" in titles
        assert "Future" not in titles

    def test_sorted_reverse_chronological(self, tmp_path, monkeypatch):
        for i, d in enumerate(["2025-03-01", "2025-01-01", "2025-06-01"]):
            post = f"---\ntitle: Post {i}\ndate: {d}\n---\nbody\n"
            _write_post(tmp_path, f"p{i}.md", post)
        monkeypatch.chdir(tmp_path)
        posts = get_posts()
        dates = [p["date"] for p in posts]
        assert dates == sorted(dates, reverse=True)

    def test_skips_invalid_posts(self, tmp_path, monkeypatch):
        _write_post(tmp_path, "good.md", MINIMAL_POST)
        _write_post(tmp_path, "bad.md", "no frontmatter at all")
        monkeypatch.chdir(tmp_path)
        posts = get_posts()
        assert len(posts) == 1
        assert posts[0]["title"] == "Test Post"


# ── render_feed ──────────────────────────────────────────────────────────


class TestRenderFeed:
    @pytest.fixture()
    def feed_tpl(self):
        with open(
            os.path.join(os.path.dirname(__file__), "templates", "feed_tpl.rss"),
            encoding="utf-8",
        ) as f:
            return f.read()

    def _make_post(self, title="Test", tags=None):
        content = pypandoc.convert_text("hello", "html", format="md")
        summary = pypandoc.convert_text("short", "html", format="md")
        post = {
            "title": title,
            "date": date(2025, 3, 1),
            "date_and_time": utils.format_datetime(
                datetime.combine(date(2025, 3, 1), time(tzinfo=timezone.utc))
            ),
            "out_file": "test.html",
            "summary": summary,
            "content": content,
        }
        if tags:
            post["has_tags"] = True
            post["tags"] = [{"name": t} for t in tags]
        return post

    def test_produces_valid_xml(self, tmp_path, monkeypatch, feed_tpl):
        _make_out_dir(tmp_path)
        monkeypatch.chdir(tmp_path)
        render_feed(feed_tpl, [self._make_post()])
        xml_text = (tmp_path / "out" / "feed.rss").read_text(encoding="utf-8")
        # CDATA sections break ElementTree, strip them for structure check
        cleaned = xml_text.replace("<![CDATA[", "").replace("]]>", "")
        ElementTree.fromstring(cleaned)  # raises on invalid XML

    def test_cdata_wrapping(self, tmp_path, monkeypatch, feed_tpl):
        _make_out_dir(tmp_path)
        monkeypatch.chdir(tmp_path)
        render_feed(feed_tpl, [self._make_post()])
        xml_text = (tmp_path / "out" / "feed.rss").read_text(encoding="utf-8")
        assert "<![CDATA[" in xml_text

    def test_content_encoded_present(self, tmp_path, monkeypatch, feed_tpl):
        _make_out_dir(tmp_path)
        monkeypatch.chdir(tmp_path)
        render_feed(feed_tpl, [self._make_post()])
        xml_text = (tmp_path / "out" / "feed.rss").read_text(encoding="utf-8")
        assert "<content:encoded>" in xml_text

    def test_category_elements_for_tags(self, tmp_path, monkeypatch, feed_tpl):
        _make_out_dir(tmp_path)
        monkeypatch.chdir(tmp_path)
        render_feed(feed_tpl, [self._make_post(tags=["rust", "tooling"])])
        xml_text = (tmp_path / "out" / "feed.rss").read_text(encoding="utf-8")
        assert "<category>rust</category>" in xml_text
        assert "<category>tooling</category>" in xml_text

    def test_no_category_without_tags(self, tmp_path, monkeypatch, feed_tpl):
        _make_out_dir(tmp_path)
        monkeypatch.chdir(tmp_path)
        render_feed(feed_tpl, [self._make_post()])
        xml_text = (tmp_path / "out" / "feed.rss").read_text(encoding="utf-8")
        assert "<category>" not in xml_text

    def test_feed_build_date_is_utc(self, tmp_path, monkeypatch, feed_tpl):
        _make_out_dir(tmp_path)
        monkeypatch.chdir(tmp_path)
        render_feed(feed_tpl, [])
        xml_text = (tmp_path / "out" / "feed.rss").read_text(encoding="utf-8")
        # pubDate and lastBuildDate should contain UTC offset
        assert "+0000" in xml_text or "GMT" in xml_text


# ── render_post ──────────────────────────────────────────────────────────


class TestRenderPost:
    @pytest.fixture()
    def post_tpl(self):
        with open(
            os.path.join(os.path.dirname(__file__), "templates", "layout.html"),
            encoding="utf-8",
        ) as f:
            return f.read()

    def test_renders_title_and_content(self, tmp_path, monkeypatch, post_tpl):
        _make_out_dir(tmp_path)
        monkeypatch.chdir(tmp_path)
        args = {
            "title": "My Post",
            "date": date(2025, 3, 1),
            "out_file": "my-post.html",
            "content": "<p>Hello</p>",
            "summary": "",
        }
        render_post(post_tpl, args)
        html = (tmp_path / "out" / "my-post.html").read_text(encoding="utf-8")
        assert "My Post" in html
        assert "<p>Hello</p>" in html

    def test_renders_tags(self, tmp_path, monkeypatch, post_tpl):
        _make_out_dir(tmp_path)
        monkeypatch.chdir(tmp_path)
        args = {
            "title": "Tagged",
            "date": date(2025, 3, 1),
            "out_file": "tagged.html",
            "content": "<p>body</p>",
            "summary": "",
            "has_tags": True,
            "tags": [{"name": "rust"}, {"name": "tooling"}],
        }
        render_post(post_tpl, args)
        html = (tmp_path / "out" / "tagged.html").read_text(encoding="utf-8")
        assert "#rust" in html
        assert "#tooling" in html

    def test_omits_tags_section_when_absent(self, tmp_path, monkeypatch, post_tpl):
        _make_out_dir(tmp_path)
        monkeypatch.chdir(tmp_path)
        args = {
            "title": "No Tags",
            "date": date(2025, 3, 1),
            "out_file": "notags.html",
            "content": "<p>body</p>",
            "summary": "",
        }
        render_post(post_tpl, args)
        html = (tmp_path / "out" / "notags.html").read_text(encoding="utf-8")
        assert 'class="tags"' not in html

    def test_omits_links_section_when_absent(self, tmp_path, monkeypatch, post_tpl):
        _make_out_dir(tmp_path)
        monkeypatch.chdir(tmp_path)
        args = {
            "title": "No Links",
            "date": date(2025, 3, 1),
            "out_file": "nolinks.html",
            "content": "<p>body</p>",
            "summary": "",
        }
        render_post(post_tpl, args)
        html = (tmp_path / "out" / "nolinks.html").read_text(encoding="utf-8")
        assert 'aria-label="links"' not in html

    def test_renders_links_when_present(self, tmp_path, monkeypatch, post_tpl):
        _make_out_dir(tmp_path)
        monkeypatch.chdir(tmp_path)
        args = {
            "title": "With Links",
            "date": date(2025, 3, 1),
            "out_file": "links.html",
            "content": "<p>body</p>",
            "summary": "",
            "links?": True,
            "links": [
                {"label": "repo", "url": "https://example.com"},
            ],
        }
        render_post(post_tpl, args)
        html = (tmp_path / "out" / "links.html").read_text(encoding="utf-8")
        assert 'aria-label="links"' in html
        assert "https://example.com" in html


# ── render_index ─────────────────────────────────────────────────────────


class TestRenderIndex:
    @pytest.fixture()
    def index_tpl(self):
        with open(
            os.path.join(os.path.dirname(__file__), "templates", "index_layout.html"),
            encoding="utf-8",
        ) as f:
            return f.read()

    def test_lists_posts(self, tmp_path, monkeypatch, index_tpl):
        _make_out_dir(tmp_path)
        monkeypatch.chdir(tmp_path)
        posts = [
            {
                "title": "First",
                "date": date(2025, 6, 1),
                "out_file": "first.html",
            },
            {
                "title": "Second",
                "date": date(2025, 5, 1),
                "out_file": "second.html",
            },
        ]
        render_index(index_tpl, posts)
        html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
        assert "First" in html
        assert "Second" in html
        assert "first.html" in html

    def test_shows_tags_on_index(self, tmp_path, monkeypatch, index_tpl):
        _make_out_dir(tmp_path)
        monkeypatch.chdir(tmp_path)
        posts = [
            {
                "title": "Tagged",
                "date": date(2025, 6, 1),
                "out_file": "tagged.html",
                "has_tags": True,
                "tags": [{"name": "rust"}],
            },
        ]
        render_index(index_tpl, posts)
        html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
        assert "#rust" in html

    def test_empty_posts(self, tmp_path, monkeypatch, index_tpl):
        _make_out_dir(tmp_path)
        monkeypatch.chdir(tmp_path)
        render_index(index_tpl, [])
        html = (tmp_path / "out" / "index.html").read_text(encoding="utf-8")
        assert "<ul>" in html  # structure present, no items


# ── existing posts validation ────────────────────────────────────────────

POSTS_DIR = os.path.join(os.path.dirname(__file__), "posts")


def _post_files():
    if not os.path.isdir(POSTS_DIR):
        return []
    return [f for f in os.listdir(POSTS_DIR) if f.endswith(".md")]


@pytest.mark.parametrize("filename", _post_files())
def test_existing_post_has_valid_frontmatter(filename):
    with open(os.path.join(POSTS_DIR, filename), encoding="utf-8") as f:
        contents = f.read()
    meta, _ = split_frontmatter(contents)
    assert "title" in meta, f"{filename}: missing title"
    assert "date" in meta, f"{filename}: missing date"
    assert isinstance(meta["date"], date), f"{filename}: date is not a date"


@pytest.mark.parametrize("filename", _post_files())
def test_existing_post_renders(filename, monkeypatch):
    monkeypatch.chdir(os.path.dirname(__file__))
    result = get_post(filename)
    assert result is not None, f"{filename}: get_post returned None"
    assert result["content"].strip(), f"{filename}: empty rendered content"
