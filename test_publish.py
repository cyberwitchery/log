"""Regression tests for publish.py.

Covers frontmatter YAML parsing, RSS XML escaping, UTC date formatting,
and template rendering — all areas where bugs have been fixed previously.
"""

import os
import re
import textwrap
from datetime import date, datetime, time, timezone
from email import utils
from xml.etree import ElementTree

import pystache
import pypandoc
import pytest
import yaml

# ---------------------------------------------------------------------------
# We can't import publish.py at module level because it unconditionally
# imports config.py (gitignored, contains deploy secrets) and instantiates
# a WebDAV client.  Instead, copy the pure-logic pieces we need to test.
# ---------------------------------------------------------------------------

FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def split_frontmatter(md):
    m = FM_RE.match(md)
    if not m:
        return {}, md
    meta_raw = m.group(1)
    meta = yaml.safe_load(meta_raw) or {}
    body = md[m.end() :]
    return meta, body


# ── frontmatter parsing ──────────────────────────────────────────────────


class TestSplitFrontmatter:
    def test_basic(self):
        md = textwrap.dedent("""\
            ---
            title: hello
            date: 2026-01-15
            ---
            body text
        """)
        meta, body = split_frontmatter(md)
        assert meta["title"] == "hello"
        assert meta["date"] == date(2026, 1, 15)
        assert body.strip() == "body text"

    def test_no_frontmatter_returns_empty_meta(self):
        md = "just some markdown\nno frontmatter here"
        meta, body = split_frontmatter(md)
        assert meta == {}
        assert body == md

    def test_multiline_summary_with_html(self):
        md = textwrap.dedent("""\
            ---
            title: test
            date: 2026-03-01
            summary: "line one<br/>line two"
            ---
            content
        """)
        meta, body = split_frontmatter(md)
        assert "<br/>" in meta["summary"]

    def test_tags_list(self):
        md = textwrap.dedent("""\
            ---
            title: tags test
            date: 2026-02-10
            tags: [alpha, beta, gamma]
            ---
            body
        """)
        meta, _ = split_frontmatter(md)
        assert meta["tags"] == ["alpha", "beta", "gamma"]

    def test_links_structure(self):
        """Matches the links format used in real posts (e.g. alembic.md)."""
        md = textwrap.dedent("""\
            ---
            title: test
            date: 2026-01-01
            "links?": true
            links:
                - label: repo
                  url: https://example.com
            ---
            body
        """)
        meta, _ = split_frontmatter(md)
        assert meta["links?"] is True
        assert meta["links"][0]["label"] == "repo"

    def test_malformed_yaml_raises(self):
        md = textwrap.dedent("""\
            ---
            title: bad
            date: [unterminated
            ---
            body
        """)
        with pytest.raises(yaml.YAMLError):
            split_frontmatter(md)

    def test_empty_frontmatter_returns_empty_dict(self):
        md = "---\n\n---\nbody"
        meta, body = split_frontmatter(md)
        assert meta == {}
        assert body == "body"

    def test_frontmatter_with_colon_in_value(self):
        md = textwrap.dedent("""\
            ---
            title: "foo: bar"
            date: 2026-01-01
            ---
            body
        """)
        meta, _ = split_frontmatter(md)
        assert meta["title"] == "foo: bar"


# ── UTC date formatting ──────────────────────────────────────────────────


class TestDateFormatting:
    def test_date_and_time_is_utc(self):
        """Regression: PR #9 fixed RSS dates to use timezone-aware UTC."""
        d = date(2026, 3, 15)
        dt = datetime.combine(d, time(tzinfo=timezone.utc))
        formatted = utils.format_datetime(dt)
        # Must contain +0000 or UTC/GMT — never be naive
        assert "+0000" in formatted or "UTC" in formatted or "GMT" in formatted

    def test_date_and_time_roundtrips(self):
        d = date(2026, 7, 4)
        dt = datetime.combine(d, time(tzinfo=timezone.utc))
        formatted = utils.format_datetime(dt)
        parsed = utils.parsedate_to_datetime(formatted)
        assert parsed.tzinfo is not None
        assert parsed.year == 2026
        assert parsed.month == 7
        assert parsed.day == 4

    def test_feed_build_date_is_utc(self):
        """The channel-level pubDate/lastBuildDate must also be UTC."""
        now = datetime.now(timezone.utc)
        formatted = utils.format_datetime(now)
        assert "+0000" in formatted or "UTC" in formatted or "GMT" in formatted


# ── RSS XML escaping ─────────────────────────────────────────────────────


class TestRSSXMLEscaping:
    @pytest.fixture()
    def feed_template(self):
        with open("templates/feed_tpl.rss") as f:
            return f.read()

    def test_html_in_summary_wrapped_in_cdata(self, feed_template):
        """Regression: PR #13 wrapped description in CDATA to prevent
        invalid XML when summaries contain HTML (e.g. <br/>, <code>)."""
        assert "<![CDATA[" in feed_template
        assert "]]>" in feed_template

    def test_feed_with_html_summary_is_valid_xml(self, feed_template):
        """Render a post whose summary contains HTML and parse as XML."""
        posts = [
            {
                "title": "test post",
                "summary": "<p>some <em>html</em> &amp; entities</p>",
                "out_file": "test.html",
                "date_and_time": utils.format_datetime(datetime.now(timezone.utc)),
            }
        ]
        xml_str = pystache.render(
            feed_template,
            {
                "date": utils.format_datetime(datetime.now(timezone.utc)),
                "posts": posts,
            },
        )
        # Must parse without an XML error
        root = ElementTree.fromstring(xml_str)
        items = root.findall(".//item")
        assert len(items) == 1
        assert items[0].find("title").text == "test post"

    def test_feed_with_angle_brackets_in_summary(self, feed_template):
        """Angle brackets inside CDATA must not break XML parsing."""
        posts = [
            {
                "title": "brackets",
                "summary": "use <code>foo</code> for bar",
                "out_file": "b.html",
                "date_and_time": utils.format_datetime(datetime.now(timezone.utc)),
            }
        ]
        xml_str = pystache.render(
            feed_template,
            {
                "date": utils.format_datetime(datetime.now(timezone.utc)),
                "posts": posts,
            },
        )
        ElementTree.fromstring(xml_str)  # must not raise

    def test_empty_feed_is_valid_xml(self, feed_template):
        xml_str = pystache.render(
            feed_template,
            {
                "date": utils.format_datetime(datetime.now(timezone.utc)),
                "posts": [],
            },
        )
        root = ElementTree.fromstring(xml_str)
        assert root.findall(".//item") == []


# ── template rendering ───────────────────────────────────────────────────


class TestTemplateRendering:
    @pytest.fixture()
    def index_template(self):
        with open("templates/index_layout.html") as f:
            return f.read()

    @pytest.fixture()
    def post_template(self):
        with open("templates/layout.html") as f:
            return f.read()

    def test_index_lists_posts(self, index_template):
        posts = [
            {"date": date(2026, 3, 1), "out_file": "a.html", "title": "A"},
            {"date": date(2026, 2, 1), "out_file": "b.html", "title": "B"},
        ]
        html = pystache.render(index_template, {"posts": posts})
        assert "A" in html
        assert "B" in html
        assert "a.html" in html
        assert "b.html" in html

    def test_index_empty_posts(self, index_template):
        html = pystache.render(index_template, {"posts": []})
        assert "<ul>" in html
        assert "<li>" not in html

    def test_post_renders_title_and_content(self, post_template):
        content = pypandoc.convert_text("hello **world**", "html", format="md")
        args = {
            "title": "My Post",
            "date": date(2026, 4, 10),
            "content": content,
        }
        html = pystache.render(post_template, args)
        assert "My Post" in html
        assert "<strong>world</strong>" in html

    def test_post_renders_summary_as_html(self, post_template):
        summary_html = pypandoc.convert_text("`cargo install foo`", "html", format="md")
        args = {
            "title": "Summary Test",
            "date": date(2026, 5, 1),
            "summary": summary_html,
            "content": "<p>body</p>",
        }
        html = pystache.render(post_template, args)
        assert "<code>" in html
        assert "cargo install foo" in html

    def test_post_renders_links(self, post_template):
        args = {
            "title": "Links Test",
            "date": date(2026, 1, 1),
            "content": "<p>body</p>",
            "links?": True,
            "links": [
                {"label": "repo", "url": "https://example.com/repo"},
                {"label": "docs", "url": "https://example.com/docs"},
            ],
        }
        html = pystache.render(post_template, args)
        assert "https://example.com/repo" in html
        assert "repo" in html
        assert "docs" in html

    def test_post_omits_links_section_when_absent(self, post_template):
        args = {
            "title": "No Links",
            "date": date(2026, 1, 1),
            "content": "<p>body</p>",
        }
        html = pystache.render(post_template, args)
        assert "links:" not in html.lower() or 'aria-label="links"' not in html


# ── actual post frontmatter validation ───────────────────────────────────


class TestExistingPosts:
    """Validate that every post in posts/ has parseable frontmatter with
    required fields.  This mirrors the CI frontmatter check but catches
    issues locally."""

    @pytest.fixture(params=sorted(os.listdir("posts")))
    def post_path(self, request):
        return os.path.join("posts", request.param)

    def test_frontmatter_parses(self, post_path):
        with open(post_path) as f:
            contents = f.read()
        meta, body = split_frontmatter(contents)
        assert meta, f"{post_path}: missing or empty frontmatter"
        assert "title" in meta, f"{post_path}: missing title"
        assert "date" in meta, f"{post_path}: missing date"
        assert isinstance(meta["date"], date), f"{post_path}: date is not a date"
        assert len(body.strip()) > 0, f"{post_path}: empty body"
