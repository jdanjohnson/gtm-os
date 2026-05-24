"""CSV parser tool — search and filter uploaded prospect lists.

Inspired by PraisonAI's CSVSearchTool. Parses CSV files and lets agents
search, filter, and extract rows matching ICP criteria.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CSVParserTool:
    """Parse and search CSV prospect lists."""

    def parse(self, file_path: str) -> dict[str, Any]:
        """Load a CSV file and return its structure + first rows."""
        path = Path(file_path)
        if not path.exists():
            return {"ok": False, "error": f"File not found: {file_path}"}
        if path.suffix.lower() != ".csv":
            return {"ok": False, "error": f"Not a CSV file: {file_path}"}
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            headers = reader.fieldnames or []
            rows = []
            for i, row in enumerate(reader):
                if i >= 100:
                    break
                rows.append(dict(row))
            return {
                "ok": True,
                "file": file_path,
                "headers": list(headers),
                "row_count": len(rows),
                "sample_rows": rows[:5],
                "all_rows": rows,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def search(
        self,
        file_path: str,
        query: str,
        column: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search a CSV for rows matching a query string."""
        parsed = self.parse(file_path)
        if not parsed["ok"]:
            return parsed
        query_lower = query.lower()
        matches = []
        for row in parsed["all_rows"]:
            if column:
                val = str(row.get(column, "")).lower()
                if query_lower in val:
                    matches.append(row)
            else:
                row_text = " ".join(str(v) for v in row.values()).lower()
                if query_lower in row_text:
                    matches.append(row)
            if len(matches) >= limit:
                break
        return {
            "ok": True,
            "query": query,
            "column": column,
            "match_count": len(matches),
            "matches": matches,
        }

    def filter_by_column(
        self,
        file_path: str,
        column: str,
        values: list[str],
        limit: int = 50,
    ) -> dict[str, Any]:
        """Filter CSV rows where a column matches any of the given values."""
        parsed = self.parse(file_path)
        if not parsed["ok"]:
            return parsed
        values_lower = {v.lower() for v in values}
        matches = []
        for row in parsed["all_rows"]:
            if str(row.get(column, "")).lower() in values_lower:
                matches.append(row)
            if len(matches) >= limit:
                break
        return {
            "ok": True,
            "column": column,
            "values": values,
            "match_count": len(matches),
            "matches": matches,
        }

    def parse_from_text(self, csv_text: str) -> dict[str, Any]:
        """Parse CSV content from a string (e.g. pasted by user)."""
        try:
            reader = csv.DictReader(io.StringIO(csv_text))
            headers = reader.fieldnames or []
            rows = [dict(row) for i, row in enumerate(reader) if i < 100]
            return {
                "ok": True,
                "headers": list(headers),
                "row_count": len(rows),
                "sample_rows": rows[:5],
                "all_rows": rows,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
