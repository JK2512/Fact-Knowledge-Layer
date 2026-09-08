"""
Fact extraction engine with dual-mode support.
- Rule-based mode: regex patterns + heuristics (always available)
- LLM mode: Gemini API for intelligent extraction (requires API key)
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from backend.models import Fact, ExtractionFailure, _new_id
from backend.confidence import calculate_evidence_confidence
from backend.config import (
    is_llm_available, GOOGLE_API_KEY, GEMINI_MODEL,
    MIN_CONFIDENCE, CONTEXT_WINDOW, LLM_CHUNK_SIZE
)

logger = logging.getLogger(__name__)

# ── Normalization Helpers ──────────────────────────────────────────────────────

# Common fiscal-year patterns
FY_PATTERN = re.compile(
    r"""(?:FY|fy)\s*'?(\d{2,4})(?:\s*[-–]\s*'?(\d{2,4}))?"""
)
YEAR_RANGE_PATTERN = re.compile(
    r"""(20\d{2})\s*[-–]\s*(\d{2,4})"""
)
QUARTER_PATTERN = re.compile(
    r"""(Q[1-4])\s*(?:FY|fy)?\s*'?(\d{2,4})""", re.IGNORECASE
)

def normalize_period(raw: str) -> str:
    """Canonicalize time period strings to a comparable form."""
    if not raw:
        return ""
    raw = raw.strip()

    # Q4 FY24 → Q4 FY2024
    m = QUARTER_PATTERN.search(raw)
    if m:
        q = m.group(1).upper()
        y = m.group(2)
        if len(y) == 2:
            y = "20" + y
        return "{} FY{}".format(q, y)

    # FY24 → FY2024, FY2023-24 → FY2024
    m = FY_PATTERN.search(raw)
    if m:
        y1 = m.group(1)
        y2 = m.group(2)
        if y2:
            if len(y2) == 2:
                y2 = y1[:2] + y2 if len(y1) == 4 else "20" + y2
            return "FY{}".format(y2)
        else:
            if len(y1) == 2:
                y1 = "20" + y1
            return "FY{}".format(y1)

    # 2023-24 → FY2024
    m = YEAR_RANGE_PATTERN.search(raw)
    if m:
        y2 = m.group(2)
        if len(y2) == 2:
            y2 = m.group(1)[:2] + y2
        return "FY{}".format(y2)

    # CY2024 or plain 2024
    m = re.search(r'(?:CY|cy)\s*(\d{4})', raw)
    if m:
        return "CY{}".format(m.group(1))

    m = re.search(r'(20\d{2})', raw)
    if m:
        return m.group(1)

    return raw.strip().upper()


def normalize_subject(raw: str) -> str:
    """Canonicalize subject names for matching."""
    if not raw:
        return ""
    s = raw.lower().strip()
    # Remove common suffixes
    for suffix in [" limited", " ltd", " ltd.", " inc", " inc.", " corp", " corporation",
                   " pvt", " private", "'s"]:
        s = s.replace(suffix, "")
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def normalize_predicate(raw: str) -> str:
    """Canonicalize predicate/attribute names."""
    if not raw:
        return ""
    s = raw.lower().strip()
    # Map common synonyms
    SYNONYMS = {
        "revenue from operations": "revenue",
        "total revenue": "revenue",
        "total income": "total_income",
        "revenue from contracts": "revenue",
        "net revenue": "revenue",
        "income from operations": "revenue",
        "gross revenue": "gross_revenue",
        "profit after tax": "pat",
        "net profit": "pat",
        "net income": "pat",
        "profit for the year": "pat",
        "profit for the period": "pat",
        "profit/(loss)": "pat",
        "profit / (loss)": "pat",
        "loss for the year": "pat",
        "loss for the period": "pat",
        "loss after tax": "pat",
        "total comprehensive income": "total_comprehensive_income",
        "ebitda": "ebitda",
        "adjusted ebitda": "adj_ebitda",
        "earnings before interest": "ebitda",
        "total expenses": "total_expenses",
        "total expenditure": "total_expenses",
        "employee benefit expense": "employee_expense",
        "employee benefits expense": "employee_expense",
        "employee cost": "employee_expense",
        "freight handling and servicing cost": "freight_cost",
        "freight and handling charges": "freight_cost",
        "depreciation and amortisation": "depreciation",
        "depreciation and amortization": "depreciation",
        "total assets": "total_assets",
        "total equity": "total_equity",
        "net worth": "net_worth",
        "share capital": "share_capital",
        "equity share capital": "share_capital",
        "gdp growth": "gdp_growth",
        "gdp growth rate": "gdp_growth",
        "real gdp growth": "real_gdp_growth",
        "nominal gdp growth": "nominal_gdp_growth",
        "cpi inflation": "cpi_inflation",
        "consumer price index": "cpi_inflation",
        "headline inflation": "cpi_inflation",
        "wpi inflation": "wpi_inflation",
        "wholesale price index": "wpi_inflation",
        "current account deficit": "cad",
        "current account balance": "cad",
        "fiscal deficit": "fiscal_deficit",
        "gross fiscal deficit": "fiscal_deficit",
        "foreign exchange reserves": "forex_reserves",
        "forex reserves": "forex_reserves",
        "fdi": "fdi",
        "foreign direct investment": "fdi",
        "exports": "exports",
        "merchandise exports": "merchandise_exports",
        "imports": "imports",
        "merchandise imports": "merchandise_imports",
        "trade deficit": "trade_deficit",
        "trade balance": "trade_deficit",
        "registered office": "registered_office",
        "corporate office": "corporate_office",
        "cin": "cin",
        "number of employees": "employee_count",
        "employee count": "employee_count",
        "headcount": "employee_count",
        "team size": "employee_count",
    }
    for key, val in SYNONYMS.items():
        if key in s:
            return val
    s = re.sub(r'[^a-z0-9\s]', '', s)
    s = re.sub(r'\s+', '_', s).strip('_')
    return s


def parse_numeric(raw: str) -> Optional[float]:
    """Parse a numeric value from a string."""
    if not raw:
        return None
    s = raw.strip()
    # Remove currency symbols and commas
    s = re.sub(r'[₹$,\s]', '', s)
    # Handle parentheses for negative numbers
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    # Remove trailing units
    s = re.sub(r'[a-zA-Z%]+$', '', s).strip()
    try:
        return float(s)
    except ValueError:
        return None


def normalize_value(value: Optional[float], unit: str) -> Optional[float]:
    """Convert value to a canonical unit for comparison.
    Canonical: Indian amounts in ₹ crore, USD in millions, percentages as-is.
    """
    if value is None:
        return None
    u = unit.lower().strip()
    # Convert to crore
    if "lakh" in u:
        return value / 100.0  # 1 crore = 100 lakh
    if "million" in u or "mn" in u:
        if "₹" in u or "inr" in u or "rupee" in u:
            return value / 10.0  # 1 crore ≈ 10 million INR
        return value  # Keep USD millions as-is
    if "billion" in u or "bn" in u:
        if "₹" in u or "inr" in u or "rupee" in u:
            return value * 100.0  # 1 billion INR = 100 crore
        if "$" in u or "usd" in u:
            return value * 1000.0  # 1 billion = 1000 million
        return value * 100.0
    if "thousand" in u:
        return value / 100000.0  # to crore
    # Already in crore or percentage or raw number
    return value


# ── Extraction Patterns ────────────────────────────────────────────────────────

# Monetary value with context
MONETARY_RE = re.compile(
    r'(?:₹|Rs\.?|INR|USD|\$|US\s*\$)\s*[\d,]+(?:\.\d+)?'
    r'\s*(?:crore|cr|lakh|lakhs|million|mn|billion|bn|thousand|'
    r'crores|millions|billions|lakhs)?',
    re.IGNORECASE
)

# Standalone large numbers with unit suffix (e.g., "8,142 crore")
NUM_UNIT_RE = re.compile(
    r'[\d,]+(?:\.\d+)?\s*(?:crore|cr|lakh|lakhs|million|mn|billion|bn|'
    r'crores|millions|billions)\b',
    re.IGNORECASE
)

# Percentage values
PERCENT_RE = re.compile(
    r'[\d.]+\s*(?:%|per\s*cent|percentage\s*points?|bps|basis\s*points?)',
    re.IGNORECASE
)

# Standalone large numbers (for table cells: "20,000" or "1,600" etc.)
LARGE_NUM_RE = re.compile(
    r'(?:^|\s)([\d,]{4,}(?:\.\d+)?)(?:\s|$)',
)

# Year / fiscal year patterns for context
PERIOD_CONTEXT_RE = re.compile(
    r'(?:FY|fy)\s*\'?\d{2,4}(?:\s*[-–]\s*\'?\d{2,4})?'
    r'|Q[1-4]\s*(?:FY|fy)?\s*\'?\d{2,4}'
    r'|20\d{2}\s*[-–]\s*\d{2,4}'
    r'|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*,?\s*20\d{2}'
    r'|20\d{2}',
    re.IGNORECASE
)


class RuleBasedExtractor:
    """Extract facts using regex patterns and heuristics."""

    def extract_from_text(
        self,
        text: str,
        page_num: int,
        doc_id: str,
        section: str = "",
        doc_title: str = "",
    ) -> Tuple[List[Fact], List[ExtractionFailure]]:
        """Extract facts from a single page of text."""
        facts = []
        failures = []

        lines = text.split('\n')
        line_offset = 0

        for line_idx, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped or len(line_stripped) < 5:
                line_offset += len(line) + 1
                continue

            # ── Monetary facts ──
            for match in MONETARY_RE.finditer(line):
                fact = self._build_fact_from_match(
                    match, line, lines, line_idx, page_num, doc_id,
                    "numerical", section, doc_title
                )
                if fact and fact.confidence >= MIN_CONFIDENCE:
                    facts.append(fact)

            # ── Standalone numeric + unit (without currency symbol) ──
            for match in NUM_UNIT_RE.finditer(line):
                # Skip if already captured by monetary pattern
                already = any(
                    f.source_text and match.group() in f.source_text
                    for f in facts[-10:]  # Check recent facts
                )
                if already:
                    continue
                fact = self._build_fact_from_match(
                    match, line, lines, line_idx, page_num, doc_id,
                    "numerical", section, doc_title
                )
                if fact and fact.confidence >= MIN_CONFIDENCE:
                    facts.append(fact)

            # ── Percentage facts ──
            for match in PERCENT_RE.finditer(line):
                fact = self._build_fact_from_match(
                    match, line, lines, line_idx, page_num, doc_id,
                    "percentage", section, doc_title
                )
                if fact and fact.confidence >= MIN_CONFIDENCE:
                    facts.append(fact)

            line_offset += len(line) + 1

        # Deduplicate: same value + same page + overlapping source text
        facts = self._deduplicate(facts)

        return facts, failures

    def extract_from_table(
        self,
        table: List[List[str]],
        page_num: int,
        doc_id: str,
        section: str = "",
        doc_title: str = "",
    ) -> List[Fact]:
        """Extract facts from a structured table."""
        facts = []
        if len(table) < 2:
            return facts

        headers = table[0]
        # Try to detect which columns contain periods/years
        period_cols = {}
        for j, h in enumerate(headers):
            if h:
                period = self._extract_period(h)
                if period:
                    period_cols[j] = period

        for i in range(1, len(table)):
            row = table[i]
            row_label = row[0] if row else ""
            if not row_label or not row_label.strip():
                continue

            subject, predicate = self._infer_from_table_label(row_label, doc_title)

            for j in range(1, len(row)):
                cell = row[j] if j < len(row) else ""
                if not cell or not cell.strip():
                    continue

                numeric = parse_numeric(cell)
                if numeric is None:
                    continue

                period = period_cols.get(j, "")
                unit = self._infer_unit_from_context(cell, row_label, headers[j] if j < len(headers) else "")
                src_text = "{}: {}".format(row_label.strip(), cell.strip())
                table_ctx = "Table in {}".format(section) if section else "Table"

                confidence, factors = calculate_evidence_confidence(
                    subject=subject,
                    predicate=predicate,
                    numeric_value=numeric,
                    unit=unit,
                    source_text=src_text,
                    context=table_ctx,
                    time_period=period,
                    source_page=page_num,
                )

                fact = Fact(
                    document_id=doc_id,
                    fact_type="numerical" if "%" not in cell else "percentage",
                    subject=subject,
                    predicate=predicate,
                    value=cell.strip(),
                    numeric_value=numeric,
                    unit=unit,
                    time_period=period,
                    confidence=confidence,
                    source_page=page_num,
                    source_text=src_text,
                    context=table_ctx,
                    normalized_subject=normalize_subject(subject),
                    normalized_predicate=normalize_predicate(predicate),
                    normalized_period=normalize_period(period),
                    normalized_value=normalize_value(numeric, unit),
                    confidence_factors=factors,
                )
                facts.append(fact)

        return facts

    def _build_fact_from_match(
        self, match, line: str, lines: List[str], line_idx: int,
        page_num: int, doc_id: str, fact_type: str,
        section: str, doc_title: str
    ) -> Optional[Fact]:
        """Build a Fact from a regex match with surrounding context."""
        raw_value = match.group().strip()
        numeric = parse_numeric(raw_value)

        # Get surrounding context for subject/predicate inference
        context_before = line[:match.start()].strip()
        context_after = line[match.end():].strip()

        # Also look at previous lines for context
        prev_lines = []
        for k in range(max(0, line_idx - 2), line_idx):
            prev_lines.append(lines[k].strip())
        context_full = " ".join(prev_lines + [line.strip()])

        # Infer subject and predicate
        subject, predicate = self._infer_subject_predicate(
            context_before, context_after, context_full, doc_title
        )

        # Extract unit
        unit = self._extract_unit(raw_value, line)

        # Extract time period
        period = self._extract_period(context_full)

        # Build source text (the sentence or surrounding context)
        source_text = self._extract_source_sentence(lines, line_idx, match)

        is_ambiguous = False
        if not subject and not predicate:
            # We found a number but can't determine what it's about
            is_ambiguous = True
            subject = doc_title or "Unknown"
            predicate = context_before[-60:] if context_before else "unidentified_metric"

        # Calculate weighted evidence confidence
        confidence, factors = self._calculate_confidence(
            subject=subject,
            predicate=predicate,
            numeric=numeric,
            unit=unit,
            source_text=source_text,
            context=section,
            time_period=period,
            source_page=page_num,
            is_ambiguous=is_ambiguous,
        )

        fact = Fact(
            document_id=doc_id,
            fact_type=fact_type,
            subject=subject,
            predicate=predicate,
            value=raw_value,
            numeric_value=numeric,
            unit=unit,
            time_period=period,
            confidence=confidence,
            source_page=page_num,
            source_text=source_text,
            context=section,
            normalized_subject=normalize_subject(subject),
            normalized_predicate=normalize_predicate(predicate),
            normalized_period=normalize_period(period),
            normalized_value=normalize_value(numeric, unit),
            confidence_factors=factors,
        )
        return fact

    def _infer_subject_predicate(
        self, before: str, after: str, full_context: str, doc_title: str
    ) -> Tuple[str, str]:
        """Infer what a fact is about from surrounding text."""
        subject = ""
        predicate = ""

        # Common patterns: "X was Y", "X of Y", "X: Y", "X stood at Y"
        # Try to extract from context before the number
        ctx = before.strip()

        # Pattern: "Revenue from operations was"
        for pattern in [
            r"((?:Revenue|Income|Profit|Loss|EBITDA|Expense|Cost|Assets?|Equity|"
            r"Liabilities|Capital|Depreciation|Amortisation|Amortization|"
            r"Shipments?|Facilities|Headcount|Employees?|GDP|GVA|"
            r"Inflation|Exports?|Imports?|Deficit|Surplus|Reserves?|FDI|"
            r"Current Account|Trade Balance|CPI|WPI|IIP)"
            r"(?:\s+\w+){0,5})",
        ]:
            m = re.search(pattern, ctx, re.IGNORECASE)
            if m:
                predicate = m.group(1).strip()
                break

        if not predicate:
            # Try the full context
            m = re.search(
                r"((?:Revenue|Income|Profit|Loss|EBITDA|Total\s+\w+|Net\s+\w+|"
                r"Gross\s+\w+|Operating\s+\w+|GDP|Inflation|Exports?|Imports?|"
                r"Deficit|Surplus|Growth|Rate|Ratio|Margin|"
                r"Reserves?|Capital|Equity|Assets?|Debt|Borrowing)"
                r"(?:\s+\w+){0,4})",
                full_context, re.IGNORECASE
            )
            if m:
                predicate = m.group(1).strip()

        if not predicate and ctx:
            # Use the last meaningful phrase before the number
            words = ctx.split()
            predicate = " ".join(words[-5:]) if len(words) > 5 else ctx
            predicate = predicate.strip("–—-:,;. ")

        # Subject inference
        # Check for company names or entity references
        entity_patterns = [
            r"(Delhivery|delhivery)",
            r"(India|Indian\s+economy|Indian)",
            r"(RBI|Reserve Bank)",
            r"(IMF|International Monetary Fund)",
            r"(Company|company|the Company|the company)",
        ]
        for pat in entity_patterns:
            m = re.search(pat, full_context)
            if m:
                subject = m.group(1)
                if subject.lower() in ("company", "the company"):
                    subject = doc_title.split()[0] if doc_title else "Company"
                break

        if not subject:
            # Default subject from doc title
            subject = doc_title.split("–")[0].split("-")[0].strip() if doc_title else ""
            if not subject:
                subject = "Document"

        return subject.strip(), predicate.strip()

    def _extract_unit(self, raw_value: str, line: str) -> str:
        """Extract the unit from a value string."""
        v = raw_value.lower()
        if "crore" in v or "cr" in v.split():
            prefix = "₹" if ("₹" in raw_value or "rs" in v or "inr" in v) else ""
            return "{} crore".format(prefix).strip()
        if "lakh" in v:
            prefix = "₹" if ("₹" in raw_value or "rs" in v or "inr" in v) else ""
            return "{} lakh".format(prefix).strip()
        if "million" in v or "mn" in v:
            prefix = "$" if ("$" in raw_value or "usd" in v) else "₹" if ("₹" in raw_value or "rs" in v) else ""
            return "{} million".format(prefix).strip()
        if "billion" in v or "bn" in v:
            prefix = "$" if ("$" in raw_value or "usd" in v) else "₹" if ("₹" in raw_value or "rs" in v) else ""
            return "{} billion".format(prefix).strip()
        # Percentage — just return % (avoid duplication like "35% %")
        if "%" in v or "per cent" in v:
            return "%"
        if "bps" in v or "basis point" in v:
            return "bps"
        if "₹" in raw_value or "rs" in v:
            # Check surrounding text for unit
            m = re.search(r'(?:crore|lakh|million|billion)', line, re.IGNORECASE)
            if m:
                return "₹ " + m.group().lower()
            return "₹"
        if "$" in raw_value or "usd" in v:
            m = re.search(r'(?:million|billion|thousand)', line, re.IGNORECASE)
            if m:
                return "$ " + m.group().lower()
            return "$"
        return ""

    def _extract_period(self, text: str) -> str:
        """Extract the time period from text context."""
        m = PERIOD_CONTEXT_RE.search(text)
        return m.group().strip() if m else ""

    def _infer_unit_from_context(self, cell: str, row_label: str, col_header: str) -> str:
        """Infer unit from table cell, row label, and column header."""
        combined = " ".join([cell, row_label, col_header]).lower()
        if "%" in cell or "%" in combined:
            return "%"
        for unit_word in ["crore", "cr", "lakh", "million", "mn", "billion", "bn"]:
            if unit_word in combined:
                prefix = "₹" if ("₹" in combined or "rs" in combined or "inr" in combined) else ""
                return "{} {}".format(prefix, unit_word).strip()
        if "₹" in combined or "rs" in combined:
            return "₹ crore"  # Default for Indian financial tables
        return ""

    def _infer_from_table_label(self, label: str, doc_title: str) -> Tuple[str, str]:
        """Infer subject and predicate from a table row label."""
        label = label.strip()
        subject = doc_title.split("–")[0].split("-")[0].strip() if doc_title else "Document"
        # Check if label mentions a specific entity
        if re.search(r'(?:India|Indian|GDP|CPI|WPI)', label, re.IGNORECASE):
            subject = "India"
        elif re.search(r'(?:Delhivery|Company)', label, re.IGNORECASE):
            subject = "Delhivery"
        predicate = label
        return subject, predicate

    def _calculate_confidence(
        self, subject: str, predicate: str,
        numeric: Optional[float], unit: str,
        source_text: str = "", context: str = "",
        time_period: str = "", source_page: int = 0,
        is_ambiguous: bool = False,
    ) -> Tuple[float, Dict[str, float]]:
        """Calculate weighted Evidence Confidence Score and factor breakdown."""
        return calculate_evidence_confidence(
            subject=subject,
            predicate=predicate,
            numeric_value=numeric,
            unit=unit,
            source_text=source_text,
            context=context,
            time_period=time_period,
            source_page=source_page,
            is_ambiguous=is_ambiguous,
        )

    def _extract_source_sentence(
        self, lines: List[str], line_idx: int, match
    ) -> str:
        """Get the source sentence/context around the match."""
        # Get the current line plus one before and after
        start = max(0, line_idx - 1)
        end = min(len(lines), line_idx + 2)
        context_lines = [l.strip() for l in lines[start:end] if l.strip()]
        text = " ".join(context_lines)
        # Trim to reasonable length
        if len(text) > 500:
            # Center around the match
            center = text.find(match.group())
            if center >= 0:
                s = max(0, center - 200)
                e = min(len(text), center + 200)
                text = text[s:e]
        return text

    def _deduplicate(self, facts: List[Fact]) -> List[Fact]:
        """Remove near-duplicate facts from the same page."""
        if not facts:
            return facts

        seen = set()
        unique = []
        for f in facts:
            key = (f.source_page, f.value, f.normalized_predicate)
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique


class LLMExtractor:
    """Extract facts using Google Gemini API."""

    def __init__(self):
        self.model = None
        if is_llm_available():
            try:
                import google.generativeai as genai
                genai.configure(api_key=GOOGLE_API_KEY)
                self.model = genai.GenerativeModel(GEMINI_MODEL)
            except Exception as e:
                logger.warning("Failed to initialize Gemini: %s", e)

    def extract_from_text(
        self,
        text: str,
        page_num: int,
        doc_id: str,
        section: str = "",
        doc_title: str = "",
    ) -> Tuple[List[Fact], List[ExtractionFailure]]:
        """Extract facts using Gemini API."""
        if not self.model:
            return [], []

        facts = []
        failures = []

        # Chunk text if too long
        chunks = [text[i:i+LLM_CHUNK_SIZE] for i in range(0, len(text), LLM_CHUNK_SIZE)]

        for chunk in chunks:
            prompt = self._build_prompt(chunk, page_num, section, doc_title)
            try:
                response = self.model.generate_content(prompt)
                extracted = self._parse_response(response.text, page_num, doc_id, doc_title)
                facts.extend(extracted)
            except Exception as e:
                failures.append(ExtractionFailure(
                    document_id=doc_id,
                    failure_type="llm_error",
                    description="Gemini API call failed: {}".format(str(e)),
                    source_page=page_num,
                    source_text=chunk[:200],
                    improvement="Retry with smaller chunks or fall back to rule-based extraction",
                ))

        return facts, failures

    def _build_prompt(self, text: str, page_num: int, section: str, doc_title: str) -> str:
        return """You are a precise fact extraction engine. Extract all factual claims from the following document text.

Document: {title}
Section: {section}
Page: {page}

For each fact, return a JSON object with these fields:
- "fact_type": one of "numerical", "percentage", "entity", "temporal", "categorical"
- "subject": what entity/topic the fact is about
- "predicate": what attribute/metric is being stated
- "value": the specific value as stated in the text
- "unit": unit of measurement (₹ crore, %, USD million, etc.) or empty
- "time_period": the relevant time period (FY2024, Q4 FY24, etc.) or empty
- "confidence": your confidence in the extraction accuracy (0.0 to 1.0)
- "source_text": the exact sentence or phrase from the text containing this fact

Return ONLY a JSON array of facts. No other text.

Important rules:
1. Extract concrete, verifiable facts — not opinions or vague statements
2. Include numerical facts (revenue, profit, counts), entity facts (directors, addresses), and categorical facts (status, classification)
3. Preserve exact values as stated — do not convert units
4. If a fact spans multiple sentences, include the most relevant one as source_text
5. For financial tables, extract each cell as a separate fact

Text:
\"\"\"
{text}
\"\"\"
""".format(
            title=doc_title,
            section=section,
            page=page_num,
            text=text
        )

    def _parse_response(
        self, response_text: str, page_num: int, doc_id: str, doc_title: str
    ) -> List[Fact]:
        """Parse Gemini's JSON response into Fact objects."""
        facts = []
        # Extract JSON from response (might be wrapped in markdown code blocks)
        json_text = response_text.strip()
        if json_text.startswith("```"):
            json_text = re.sub(r'^```\w*\n?', '', json_text)
            json_text = re.sub(r'\n?```$', '', json_text)

        try:
            items = json.loads(json_text)
        except json.JSONDecodeError:
            # Try to find JSON array in the response
            m = re.search(r'\[.*\]', json_text, re.DOTALL)
            if m:
                try:
                    items = json.loads(m.group())
                except json.JSONDecodeError:
                    return facts
            else:
                return facts

        if not isinstance(items, list):
            items = [items]

        for item in items:
            if not isinstance(item, dict):
                continue
            value = str(item.get("value", ""))
            numeric = parse_numeric(value)
            unit = item.get("unit", "")
            period = item.get("time_period", "")
            subject = item.get("subject", doc_title)
            predicate = item.get("predicate", "")

            conf, factors = calculate_evidence_confidence(
                subject=subject,
                predicate=predicate,
                numeric_value=numeric,
                unit=unit,
                source_text=item.get("source_text", ""),
                context="LLM extraction",
                time_period=period,
                source_page=page_num,
            )

            fact = Fact(
                document_id=doc_id,
                fact_type=item.get("fact_type", "numerical"),
                subject=subject,
                predicate=predicate,
                value=value,
                numeric_value=numeric,
                unit=unit,
                time_period=period,
                confidence=conf,
                source_page=page_num,
                source_text=item.get("source_text", ""),
                context="LLM extraction",
                normalized_subject=normalize_subject(subject),
                normalized_predicate=normalize_predicate(predicate),
                normalized_period=normalize_period(period),
                normalized_value=normalize_value(numeric, unit),
                confidence_factors=factors,
            )
            facts.append(fact)

        return facts


# ── Main Extraction Pipeline ──────────────────────────────────────────────────

class FactExtractor:
    """Orchestrates fact extraction from a PDF using available methods."""

    def __init__(self):
        self.rule_extractor = RuleBasedExtractor()
        self.llm_extractor = LLMExtractor() if is_llm_available() else None
        self.mode = "llm" if (self.llm_extractor and self.llm_extractor.model) else "rule_based"

    def extract(
        self,
        pages: List[Dict[str, Any]],
        tables: Dict[int, List[List[List[str]]]],
        doc_id: str,
        doc_title: str = "",
    ) -> Tuple[List[Fact], List[ExtractionFailure]]:
        """Extract facts from all pages and tables of a document."""
        all_facts = []
        all_failures = []

        for page_info in pages:
            text = page_info["text"]
            page_num = page_info["page_number"]
            section = page_info.get("section", "")
            page_idx = page_info["page_index"]

            if not text or len(text.strip()) < 20:
                continue

            # Extract from text
            if self.mode == "llm" and self.llm_extractor:
                facts, failures = self.llm_extractor.extract_from_text(
                    text, page_num, doc_id, section, doc_title
                )
                # Also run rule-based for comparison / supplementation
                rb_facts, rb_failures = self.rule_extractor.extract_from_text(
                    text, page_num, doc_id, section, doc_title
                )
                # Merge: prefer LLM facts but add unique rule-based ones
                facts = self._merge_facts(facts, rb_facts)
                failures.extend(rb_failures)
            else:
                facts, failures = self.rule_extractor.extract_from_text(
                    text, page_num, doc_id, section, doc_title
                )

            all_facts.extend(facts)
            all_failures.extend(failures)

            # Extract from tables on this page
            if page_idx in tables:
                for table in tables[page_idx]:
                    table_facts = self.rule_extractor.extract_from_table(
                        table, page_num, doc_id, section, doc_title
                    )
                    all_facts.extend(table_facts)

        # Final deduplication across all pages
        all_facts = self._global_deduplicate(all_facts)

        logger.info("Extracted %d facts (%d failures) from %s",
                     len(all_facts), len(all_failures), doc_title)
        return all_facts, all_failures

    def _merge_facts(self, primary: List[Fact], secondary: List[Fact]) -> List[Fact]:
        """Merge two fact lists, preferring primary but adding unique secondary facts."""
        if not primary:
            return secondary
        if not secondary:
            return primary

        # Index primary facts by (page, value)
        primary_keys = set()
        for f in primary:
            primary_keys.add((f.source_page, f.value))

        merged = list(primary)
        for f in secondary:
            key = (f.source_page, f.value)
            if key not in primary_keys:
                merged.append(f)

        return merged

    def _global_deduplicate(self, facts: List[Fact]) -> List[Fact]:
        """Remove duplicate facts across all pages."""
        seen = set()
        unique = []
        for f in facts:
            # Key on normalized attributes
            key = (f.document_id, f.normalized_predicate, f.value,
                   f.normalized_period, f.source_page)
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique
