"""PraisonAI-inspired research tools for GTM campaigns.

Built without PraisonAI as a dependency. Each tool is self-contained and
follows the GTM-OS Tool interface (async callable returning dict).

Tools:
- browser: Fetch and extract text from web pages
- scraper: Structured data extraction (emails, phones, social links, headings)
- search: Google search via Serper.dev or Brave Search API
- csv_parser: Search and filter CSV prospect lists
- pdf_parser: Extract and search text from PDF reports
- youtube: Search YouTube channels for prospect content
"""

from .browser import BrowserTool
from .csv_parser import CSVParserTool
from .pdf_parser import PDFParserTool
from .scraper import WebScraperTool
from .search import WebSearchTool
from .youtube import YouTubeSearchTool

__all__ = [
    "BrowserTool",
    "CSVParserTool",
    "PDFParserTool",
    "WebScraperTool",
    "WebSearchTool",
    "YouTubeSearchTool",
]
