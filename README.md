# Fact Knowledge Layer (FKL)
### Cross-Document Fact Verification, Evidence Relationship Graph & Contradiction-Aware RAG

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-green.svg)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey.svg)](https://sqlite.org/)
[![Status](https://img.shields.io/badge/Tests-17%2F17%20Passed-brightgreen.svg)]()

The **Fact Knowledge Layer (FKL)** is an evidence-grounded knowledge intelligence platform designed to extract, normalize, link, and reconcile facts across heterogeneous PDF documents. It couples deterministic entity-metric relationship linking with an interactive **Evidence Relationship Graph**, **Hybrid Retrieval** (Structured SQL + Lexical BM25), a **Contradiction-Aware RAG Engine**, and **Deterministic Post-Generation Evidence Validation**.

---

## 🏛 Architecture

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

## ⚡ Why Not Just Traditional Vector RAG?

Standard vector RAG divides documents into arbitrary text chunks, embeds them into high-dimensional vector spaces, and passes top-$k$ chunks directly to an LLM. While easy to build, this approach fails in cross-document financial and quantitative analysis:

| Failure Mode | Traditional Vector RAG | Fact Knowledge Layer (FKL) |
| :--- | :--- | :--- |
| **Contradictions** | LLM silently picks one source or averages conflicting numbers without warning the user. | **Deterministic FactLinker** detects metric discrepancies, marks `CONTRADICTION`, and preserves both claims with source evidence. |
| **Contextual Reconciliation** | Misinterprets quarterly vs annual or standalone vs consolidated figures as direct errors. | Recognizes **Contextual Differences** (period shifts, accounting definitions, revisions) and explains the reconciliation. |
| **Source Grounding** | LLM paraphrases citations or hallucinates page numbers. | Every fact is strictly bound to its **exact page number, verbatim sentence quote, and document ID**. |
| **Hallucination Prevention** | Relies on LLM prompt instructions ("don't lie"). | **Deterministic Evidence Validator** scans every generated metric and rejects ungrounded numbers. |
| **Offline Independence** | Requires constant API connectivity to external LLM providers. | **100% functional offline** via deterministic template synthesis and local BM25 + SQL indexing. |
| **Infrastructure Overhead** | Requires heavy vector DBs (Pinecone, Weaviate), graph DBs (Neo4j), or microservices. | **Lightweight zero-dependency architecture** running locally on Python + SQLite. |

---

## 🧩 Core Capabilities

### 1. Multi-Modal Document Parser & Normalizer
- High-speed text extraction and layout-aware table parser powered by PyMuPDF.
- Standardizes financial numbers into canonical formats (e.g. ₹ Crores, Millions, Billions, Percentages).
- Standardizes time horizons into canonical formats (e.g., `FY2024`, `Q4 FY2024`, `CY2024`, `March 2024`).

### 2. Deterministic Fact Linking & Relationship Semantics
Cross-document facts are linked based on subject entity, metric predicate, and period alignment:
- **`CORROBORATION`**: Independent documents report matching values within a 5% margin of error.
- **`CONTRADICTION`**: Independent documents report conflicting values for the identical entity, metric, and period without contextual qualification.
- **`CONTEXTUAL_DIFFERENCE` / `RECONCILIATION`**: Figures differ on the surface but are reconciled by distinct time horizons, standalone vs consolidated accounting, or estimate revisions.
- **`UNCERTAIN`**: Ambiguous statements lacking critical unit or header context are explicitly flagged rather than guessed.

### 3. Logical Evidence Relationship Graph
- Accessible via `/api/graph` and visually interactive in the UI.
- Nodes represent Documents and Structured Facts; Edges represent evidence citations and cross-document relationships (Corroboration, Contradiction, Reconciliation).
- Built dynamically on top of SQLite facts and relationships without requiring an external graph database.

### 4. Hybrid Retrieval Engine
Combines the precision of structured relational filters with the breadth of lexical search:
1. **Structured SQL Retrieval**: Queries the database by subject, metric predicate, canonical period, and fact type.
2. **Lexical BM25 Retrieval**: Matches natural-language question tokens against compact, enriched fact-evidence cards.
3. **Merge & Relationship Attachment**: Deduplicates retrieved facts, computes reciprocal rank fusion scores, and pulls all connected cross-document relationships.

### 5. Contradiction-Aware RAG Synthesis
- **Offline Deterministic Synthesis**: Synthesizes verified multi-source answers, highlighting agreements, conflicts, and reconciliations directly from relationship reasoning.
- **Optional Gemini LLM Synthesis**: When an API key is present, LLM synthesis enhances linguistic fluency while strictly constrained to the retrieved fact bundle.

### 6. Post-Generation Evidence Validator
- Operates after generation to guarantee zero factual hallucination.
- Extracts all numerical values, percentages, periods, and document references from the synthesized answer.
- Validates that every extracted token is grounded in the retrieved facts, verbatim quotes, or relationship reasoning.
- Flags ungrounded answers with `UNSUPPORTED_METRIC_DETECTED` and lowers confidence.

---

## 🧪 Demonstration of the 4 Core Cases

| Scenario | Input / Query | Ground Truth Ingested | Output & Verification |
| :--- | :--- | :--- | :--- |
| **Case 1: Corroboration** | `"Which sources corroborate Delhivery's FY24 express parcel shipment volume?"` | • Delhivery Annual Report FY24 (p. 36 / 11): **740 million parcels**<br>• Delhivery Q4 FY24 Presentation (p. 6): **740 Mn** | ✅ Status: `CORROBORATION`<br>Highlights full agreement on **740M shipments** across both sources with exact page quotes. |
| **Case 2: Contradiction** | `"Do the sources agree on India's FY25 real GDP growth?"` | • Economic Survey 2024-25 (p. 1 & 11): **6.4%**<br>• RBI Annual Report 2024-25 (p. 3): **6.5%**<br>• IMF Article IV 2025 (p. 5): **6.5%** | ⚠️ Status: `CONTRADICTION` (6.4% vs 6.5%) & `CORROBORATION` (RBI ↔ IMF 6.5%)<br>Refuses to average or pick one number; presents both conflicting figures with exact source citations. |
| **Case 3: Contextual Reconciliation** | `"Why do the fiscal deficit figures differ across the sources?"` | • RBI Annual Report 2024-25 (p. 64): **4.7%** (General Govt GFD)<br>• IMF Article IV 2025 (p. 5): **4.9%** (Central Govt Deficit) | 🔄 Status: `CONTEXTUAL_DIFFERENCE`<br>Explains difference due to distinct reporting definitions and accounting scopes. |
| **Case 4: Uncertainty Handling** | `"Can the 81,417.43 revenue value be safely interpreted?"` | • Prospectus / Table cell: **81,417.43** (ambiguous / missing header context) | ❓ Status: `UNCERTAIN`<br>Explicitly refuses to guess whether value represents ₹ crore or ₹ million without explicit evidence. |

---

## 🚀 Quickstart & Setup

### Prerequisites
- Python 3.10+
- Modern Web Browser (Chrome, Firefox, Edge, Safari)

### 1. Installation
Clone the repository and install the lightweight dependencies:
```bash
git clone https://github.com/your-repo/superjoin2.git
cd superjoin2
pip install -r requirements.txt
```

### 2. Start the Application
Run the FastAPI backend:
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Open your browser and navigate to:
```
http://localhost:8000
```

### 3. Run the Interactive 4-Case Demo CLI
Run all 4 core assignment demo cases with verification telemetry in a single command:
```bash
python run_demo.py
```

### 4. Run the Full Test Suite
Execute the comprehensive automated test suite (17 automated tests covering retrieval, RAG cases, validation, incremental linking, and APIs):
```bash
python -m unittest discover tests/ -v
```

---

## 📡 API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/upload` | Upload and incrementally ingest a PDF document |
| `POST` | `/api/query` | Contradiction-aware natural language question answering with hybrid retrieval and validation |
| `GET` | `/api/graph` | Retrieve visual evidence graph nodes and edges for UI visualization |
| `GET` | `/api/documents` | List all ingested documents and metadata |
| `GET` | `/api/facts` | Query structured facts with search, type, and document filters |
| `GET` | `/api/relationships` | Retrieve cross-document relationships with verbatim evidence quotes |
| `POST` | `/api/analyze` | Re-run full cross-document correlation analysis |
| `GET` | `/api/failures` | List extraction failures and uncertainty audit logs |
| `GET` | `/api/stats` | System-wide statistics and relationship breakdown |

---

## 🖥 Web Interface

The web interface is organized into 5 dedicated views:
1. **💬 Ask Knowledge Base**: Interactive natural language query interface with 1-click sample chips, visual confidence badges, evidence validation audit badges, and expandable source quotes.
2. **🕸 Evidence Graph**: Interactive force-directed canvas visualizing cross-document connections, corroborations, contradictions, and reconciliations.
3. **📊 Dashboard**: High-level telemetry, document counts, fact totals, and relationship distributions.
4. **📄 Documents & Facts**: Searchable and filterable data tables displaying structured facts, normalized numbers, and verbatim evidence snippets.
5. **🔗 Relationships & Discrepancies**: Dedicated cross-document analysis table with filter tabs for Corroboration, Contradiction, and Contextual Differences.
