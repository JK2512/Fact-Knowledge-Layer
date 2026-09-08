"""
PDF text extraction using PyMuPDF.
Handles page-by-page extraction, table detection, and metadata.
"""

import re
import fitz  # PyMuPDF
from typing import List, Dict, Any, Tuple
from pathlib import Path


class PDFParser:
    """Extract structured text and metadata from PDF files."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.doc = fitz.open(filepath)

    def close(self):
        self.doc.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def page_count(self) -> int:
        return len(self.doc)

    def get_metadata(self) -> Dict[str, Any]:
        """Extract PDF metadata."""
        meta = self.doc.metadata or {}
        return {
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "creator": meta.get("creator", ""),
            "producer": meta.get("producer", ""),
            "page_count": self.page_count,
        }

    def get_title(self) -> str:
        """Try to infer a document title from metadata or first page."""
        meta = self.doc.metadata or {}
        title = meta.get("title", "").strip()
        if title:
            return title

        # Try to extract from first page — look for large text
        if self.page_count > 0:
            page = self.doc[0]
            blocks = page.get_text("dict")["blocks"]
            max_size = 0
            title_text = ""
            for block in blocks:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        text_str = span["text"].strip()
                        # Only consider text that looks like a title (>3 chars, not just a name)
                        if (span["size"] > max_size and len(text_str) > 3
                                and not re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+$', text_str)):
                            max_size = span["size"]
                            title_text = text_str
            if title_text and len(title_text) > 5:
                return title_text

        # Fallback: generate clean title from filename
        return self._title_from_filename()

    def _title_from_filename(self) -> str:
        """Generate a readable title from the filename."""
        stem = Path(self.filepath).stem
        # Remove numbering prefix like "01-" or "02-"
        stem = re.sub(r'^\d{1,3}[-_]', '', stem)
        # Replace hyphens and underscores with spaces
        stem = stem.replace('-', ' ').replace('_', ' ')
        # Title case
        return stem.title()

    def extract_page_text(self, page_num: int) -> str:
        """Extract text from a specific page (0-indexed)."""
        if page_num < 0 or page_num >= self.page_count:
            return ""
        page = self.doc[page_num]
        text = page.get_text("text")
        # Clean up common PDF artifacts
        text = self._clean_text(text)
        return text

    def extract_all_text(self) -> List[Dict[str, Any]]:
        """Extract text from all pages with page numbers."""
        pages = []
        for i in range(self.page_count):
            page = self.doc[i]
            text = page.get_text("text")
            text = self._clean_text(text)

            # Get the printed page number if visible
            printed_page = self._detect_page_number(text, i)

            # Detect section headings on this page
            section = self._detect_section(page)

            pages.append({
                "page_index": i,
                "page_number": printed_page,
                "text": text,
                "section": section,
                "char_count": len(text),
            })
        return pages

    def extract_tables(self, page_num: int) -> List[List[List[str]]]:
        """Extract structured tables from a specific page using fast text layout analysis."""
        if page_num < 0 or page_num >= self.page_count:
            return []
        page = self.doc[page_num]
        text = page.get_text("text")
        lines = text.split("\n")
        
        tables = []
        curr_table = []
        for line in lines:
            line_str = line.strip()
            if not line_str:
                if len(curr_table) >= 2:
                    tables.append(curr_table)
                curr_table = []
                continue
            
            # Check for multiple whitespace/tab columns
            parts = [self._clean_cell(p) for p in re.split(r'\s{2,}|\t', line_str) if p.strip()]
            if len(parts) >= 2:
                curr_table.append(parts)
            else:
                # Check if line contains space-separated tokens with numeric data
                tokens = [self._clean_cell(t) for t in line_str.split() if t.strip()]
                if len(tokens) >= 2 and any(re.match(r'^-?[\d,]+(?:\.\d+)?%?$', t) for t in tokens[1:]):
                    curr_table.append(tokens)
                else:
                    if len(curr_table) >= 2:
                        tables.append(curr_table)
                    curr_table = []
        if len(curr_table) >= 2:
            tables.append(curr_table)
            
        return tables

    def extract_all_tables(self) -> Dict[int, List[List[List[str]]]]:
        """Extract tables from all pages."""
        all_tables = {}
        for i in range(self.page_count):
            tables = self.extract_tables(i)
            if tables:
                all_tables[i] = tables
        return all_tables

    def _clean_text(self, text: str) -> str:
        """Clean extracted text of common PDF artifacts."""
        # Remove excessive whitespace but preserve paragraph breaks
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Remove common PDF artifacts
        text = text.replace('\x00', '')
        text = re.sub(r'(?<=[a-z])-\n(?=[a-z])', '', text)  # Fix hyphenation
        return text.strip()

    def _clean_cell(self, cell) -> str:
        """Clean a table cell value."""
        if cell is None:
            return ""
        s = str(cell).strip()
        s = re.sub(r'\s+', ' ', s)
        return s

    def _detect_page_number(self, text: str, index: int) -> int:
        """Try to detect the printed page number from text."""
        lines = text.strip().split('\n')
        # Check last few lines for standalone numbers (common page number location)
        for line in reversed(lines[-3:]):
            line = line.strip()
            if re.match(r'^\d{1,4}$', line):
                try:
                    return int(line)
                except ValueError:
                    pass
        # Check first few lines too
        for line in lines[:3]:
            line = line.strip()
            if re.match(r'^\d{1,4}$', line):
                try:
                    return int(line)
                except ValueError:
                    pass
        return index + 1  # Fallback to 1-indexed

    def _detect_section(self, page) -> str:
        """Detect the section heading on a page by looking for large/bold text."""
        blocks = page.get_text("dict")["blocks"]
        candidates = []
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                line_text = ""
                max_size = 0
                is_bold = False
                for span in line["spans"]:
                    line_text += span["text"]
                    max_size = max(max_size, span["size"])
                    if "bold" in span.get("font", "").lower():
                        is_bold = True
                line_text = line_text.strip()
                if line_text and max_size > 11 and len(line_text) < 120:
                    candidates.append((max_size, is_bold, line_text))

        if not candidates:
            return ""

        # Return the largest text that looks like a heading
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return candidates[0][2]
