"""Tests for PraisonAI-inspired research tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from gtm_os.engine.research_tools.browser import BrowserTool, _extract_title, _html_to_text
from gtm_os.engine.research_tools.csv_parser import CSVParserTool
from gtm_os.engine.research_tools.pdf_parser import PDFParserTool
from gtm_os.engine.research_tools.scraper import WebScraperTool
from gtm_os.engine.research_tools.search import WebSearchTool
from gtm_os.engine.research_tools.youtube import YouTubeSearchTool


class TestBrowserTool:
    def test_html_to_text_strips_tags(self):
        html = "<p>Hello <b>world</b></p>"
        assert "Hello" in _html_to_text(html)
        assert "world" in _html_to_text(html)
        assert "<b>" not in _html_to_text(html)

    def test_html_to_text_removes_scripts(self):
        html = "<script>alert('xss')</script><p>Content</p>"
        text = _html_to_text(html)
        assert "alert" not in text
        assert "Content" in text

    def test_extract_title(self):
        html = "<html><head><title>My Page</title></head><body>Hi</body></html>"
        assert _extract_title(html) == "My Page"

    def test_extract_title_empty(self):
        assert _extract_title("<html><body>No title</body></html>") == ""

    def test_fetch_invalid_url(self):
        browser = BrowserTool(timeout=3)
        result = browser.fetch("http://this-domain-does-not-exist-12345.example")
        assert not result["ok"]
        assert "error" in result


class TestWebScraperTool:
    def test_scrape_invalid_url(self):
        scraper = WebScraperTool(timeout=3)
        result = scraper.scrape("http://this-domain-does-not-exist-12345.example")
        assert not result["ok"]


class TestWebSearchTool:
    def test_search_no_api_key(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("SERPER_API_KEY", raising=False)
        monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
        tool = WebSearchTool()
        result = tool.search("test query")
        assert not result["ok"]
        assert "No search API key" in result["error"]


class TestCSVParserTool:
    def test_parse_csv(self, tmp_path: Path):
        csv_file = tmp_path / "prospects.csv"
        csv_file.write_text("name,email,title\nAlice,alice@co.com,CEO\nBob,bob@co.com,CTO\n")
        tool = CSVParserTool()
        result = tool.parse(str(csv_file))
        assert result["ok"]
        assert result["headers"] == ["name", "email", "title"]
        assert result["row_count"] == 2

    def test_search_csv(self, tmp_path: Path):
        csv_file = tmp_path / "prospects.csv"
        csv_file.write_text("name,email,title\nAlice,alice@co.com,CEO\nBob,bob@co.com,CTO\n")
        tool = CSVParserTool()
        result = tool.search(str(csv_file), "alice")
        assert result["ok"]
        assert result["match_count"] == 1
        assert result["matches"][0]["name"] == "Alice"

    def test_search_csv_by_column(self, tmp_path: Path):
        csv_file = tmp_path / "prospects.csv"
        csv_file.write_text("name,email,title\nAlice,alice@co.com,CEO\nBob,bob@co.com,CTO\n")
        tool = CSVParserTool()
        result = tool.search(str(csv_file), "CEO", column="title")
        assert result["ok"]
        assert result["match_count"] == 1

    def test_filter_by_column(self, tmp_path: Path):
        csv_file = tmp_path / "prospects.csv"
        csv_file.write_text("name,email,title\nAlice,a@co.com,CEO\nBob,b@co.com,CTO\nCat,c@co.com,CEO\n")
        tool = CSVParserTool()
        result = tool.filter_by_column(str(csv_file), "title", ["CEO"])
        assert result["ok"]
        assert result["match_count"] == 2

    def test_parse_missing_file(self):
        tool = CSVParserTool()
        result = tool.parse("/nonexistent/file.csv")
        assert not result["ok"]

    def test_parse_from_text(self):
        tool = CSVParserTool()
        result = tool.parse_from_text("name,email\nAlice,a@co.com\n")
        assert result["ok"]
        assert result["row_count"] == 1


class TestPDFParserTool:
    def test_missing_file(self):
        tool = PDFParserTool()
        result = tool.extract("/nonexistent/file.pdf")
        assert not result["ok"]

    def test_wrong_extension(self, tmp_path: Path):
        txt = tmp_path / "file.txt"
        txt.write_text("not a pdf")
        tool = PDFParserTool()
        result = tool.extract(str(txt))
        assert not result["ok"]
        assert "Not a PDF" in result["error"]


class TestYouTubeSearchTool:
    def test_fallback_no_keys(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        monkeypatch.delenv("SERPER_API_KEY", raising=False)
        monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
        tool = YouTubeSearchTool()
        result = tool.search_videos("test")
        # Should fall back to web search, which will also fail without API keys.
        assert "error" in result or "results" in result

    def test_channel_info_no_key(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        tool = YouTubeSearchTool()
        result = tool.get_channel_info("UC123")
        assert not result["ok"]
