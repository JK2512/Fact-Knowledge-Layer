# Fact Knowledge Layer: System Architecture

## Overview
The **Fact Knowledge Layer (FKL)** is an evidence-backed knowledge intelligence platform that extracts, normalizes, links, and reconciles facts across heterogeneous PDF documents. It features hybrid retrieval (Structured SQL + Lexical BM25 search), a logical Evidence Relationship Graph, a contradiction-aware RAG query layer, and deterministic post-generation evidence validation.

---

## Core Pipeline

```
                    ┌──────────────┐
                    │  PDF Upload  │ (Single or batch PDF ingestion)
                    └──────┬───────┘
                           ↓
                 ┌──────────────────┐
                 │ Multi-modal      │ (PyMuPDF high-speed text + layout table parser)
                 │ Document Parser  │
                 └────────┬─────────┘
                          ↓
                 ┌──────────────────┐
                 │ Fact Extraction  │ (Dual-mode: Heuristic regex + Gemini LLM fallback)
                 │ Regex + LLM      │
                 └────────┬─────────┘
                          ↓
              ┌─────────────────────────┐
              │ FACT KNOWLEDGE LAYER    │ (Authoritative Ground Truth)
              │                         │
              │ • Structured Facts      │ (4,522 facts across 6 PDFs)
              │ • Normalized Values     │ (Standardized to INR ₹ Cr, USD Mn, %)
              │ • Canonical Periods     │ (FY2024, Q4 FY2024, CY2024)
              │ • Source Metadata       │ (Document name, page number, context)
              │ • Verbatim Evidence     │ (Exact sentence quotes from document)
              └────────────┬────────────┘
                           ↓
                 ┌──────────────────┐
                 │ Fact Linker      │ (Cross-document entity & metric comparison)
                 └────────┬─────────┘
                          ↓
       ┌──────────────────┼──────────────────┐
       ↓                  ↓                  ↓
 Corroboration       Contradiction      Contextual Difference
 [1,199 links]        [145 links]          [4,489 links]
       └──────────────────┼──────────────────┘
                          ↓
                 ┌──────────────────┐
                 │ Evidence Graph   │ (Logical graph connecting Facts, Docs & Edges)
                 └────────┬─────────┘
                          ↓
                 ┌──────────────────┐
                 │ Hybrid Retrieval │
                 │ ┌──────────────┐ │
                 │ │Structured SQL│ │
                 │ └──────┬───────┘ │
                 │        +         │
                 │ ┌──────▼───────┐ │
                 │ │Lexical BM25  │ │
                 │ └──────────────┘ │
                 └────────┬─────────┘
                          ↓
                 ┌──────────────────┐
                 │ RAG Query Layer  │ (Contradiction-aware natural language synthesis)
                 └────────┬─────────┘
                          ↓
                 ┌──────────────────┐
                 │ Evidence         │ (Deterministic post-generation verification)
                 │ Validator        │ (Catches ungrounded numbers & hallucinations)
                 └────────┬─────────┘
                          ↓
              Evidence-Backed Answer
```

---

## Key Principles & Design Decisions

### 1. Structured Facts as the Source of Truth
- Traditional RAG systems blindly chunk documents into vector embeddings and feed raw text to an LLM, making them susceptible to hallucinations and unable to spot direct numerical contradictions.
- In FKL, **structured facts and verbatim evidence are the primary source of truth**. RAG serves only as the natural-language query and explanation layer.

### 2. Contradiction & Reconciliation Semantics
- **Corroboration**: Facts from different documents that agree on the same metric, subject, and time period within a configured tolerance (e.g. 5%).
- **Contradiction**: Facts from different documents that report conflicting figures for the same entity, metric, and time period.
- **Contextual Reconciliation**: Figures that differ on the surface but are explained by contextual factors:
  - Different reporting timeframes (e.g., FY21 vs FY24)
  - Different accounting standards or definitions (e.g., Standalone vs Consolidated)
  - Revisions or advance estimates vs final actuals
  - Different measurement units (e.g., ₹ crore vs USD million)
- **Uncertainty**: Ambiguous facts where required unit or header context is missing are explicitly flagged as uncertain rather than guessed.

### 3. Evidence Validation Engine
- Runs after answer generation.
- Scans all numerical values, percentages, periods, and document references in the answer.
- Cross-checks each value against the retrieved ground-truth facts, relationship reasoning, and verbatim evidence snippets.
- If any unsupported metric is detected, the answer is flagged as `UNSUPPORTED_METRIC_DETECTED` with `confidence = LOW` or rejected.

### 4. Incremental Indexing
- When a new PDF is uploaded, only the new document's text is parsed and extracted.
- Newly extracted facts are compared incrementally against existing database facts.
- Existing documents, facts, and relationships remain intact without full database wipes or reprocessing.

---

## API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/upload` | Upload and incrementally ingest a PDF document |
| `POST` | `/api/query` | Natural language question answering with hybrid retrieval and validation |
| `GET` | `/api/graph` | Retrieve visual evidence graph nodes and edges |
| `GET` | `/api/documents` | List all ingested documents |
| `GET` | `/api/facts` | Query structured facts with search, type, and document filters |
| `GET` | `/api/relationships` | Retrieve cross-document relationships with verbatim evidence |
| `POST` | `/api/analyze` | Re-run full cross-document correlation analysis |
| `GET` | `/api/failures` | List extraction failures and uncertainty logs |
| `GET` | `/api/stats` | System-wide statistics and breakdown |
