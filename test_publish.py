from publish import sanitize_slug, SLUG_RE


class TestSlugRegex:
    def test_simple_alpha(self):
        assert SLUG_RE.match("hello")

    def test_alphanumeric(self):
        assert SLUG_RE.match("post123")

    def test_hyphens(self):
        assert SLUG_RE.match("my-post")

    def test_underscores(self):
        assert SLUG_RE.match("my_post")

    def test_dots(self):
        assert SLUG_RE.match("infrahub.rs")

    def test_rejects_path_traversal(self):
        assert not SLUG_RE.match("../../../etc/passwd")

    def test_rejects_leading_dot(self):
        assert not SLUG_RE.match(".hidden")

    def test_rejects_slash(self):
        assert not SLUG_RE.match("foo/bar")

    def test_rejects_backslash(self):
        assert not SLUG_RE.match("foo\\bar")

    def test_rejects_empty(self):
        assert not SLUG_RE.match("")

    def test_rejects_space(self):
        assert not SLUG_RE.match("my post")

    def test_rejects_null_byte(self):
        assert not SLUG_RE.match("foo\x00bar")


class TestSanitizeSlug:
    def test_valid_slug_passes_through(self):
        assert sanitize_slug("my-post", "fallback", "test.md") == "my-post"

    def test_dotted_slug_passes(self):
        assert sanitize_slug("nautobot.rs", "nautobot", "nautobot.md") == "nautobot.rs"

    def test_path_traversal_falls_back(self, capsys):
        result = sanitize_slug("../../../etc/passwd", "safe", "evil.md")
        assert result == "safe"
        assert "bad slug" in capsys.readouterr().err

    def test_slash_in_slug_falls_back(self, capsys):
        result = sanitize_slug("sub/dir", "fallback", "test.md")
        assert result == "fallback"
        assert "bad slug" in capsys.readouterr().err

    def test_leading_dot_falls_back(self, capsys):
        result = sanitize_slug(".htaccess", "fallback", "test.md")
        assert result == "fallback"
        assert "bad slug" in capsys.readouterr().err

    def test_bad_slug_bad_fallback_returns_none(self, capsys):
        result = sanitize_slug("../evil", "../also-evil", "test.md")
        assert result is None
        assert "no safe fallback" in capsys.readouterr().err

    def test_empty_slug_falls_back(self, capsys):
        result = sanitize_slug("", "fallback", "test.md")
        assert result == "fallback"
        assert "bad slug" in capsys.readouterr().err

    def test_backslash_falls_back(self, capsys):
        result = sanitize_slug("foo\\bar", "fallback", "test.md")
        assert result == "fallback"
        assert "bad slug" in capsys.readouterr().err
