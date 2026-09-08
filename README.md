# Fact Knowledge Layer (FKL)
### Cross-Document Fact Verification, Evidence Relationship Graph & Contradiction-Aware RAG

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-green.svg)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey.svg)](https://sqlite.org/)
[![Status](https://img.shields.io/badge/Tests-25%2F25%20Passed-brightgreen.svg)]()

The **Fact Knowledge Layer (FKL)** is an evidence-grounded knowledge intelligence platform designed to extract, normalize, link, and reconcile facts across heterogeneous PDF documents. It couples deterministic entity-metric relationship linking with an interactive **Evidence Relationship Graph**, **Hybrid Retrieval** (Structured SQL + Lexical BM25), a **Contradiction-Aware RAG Engine**, and **Deterministic Post-Generation Evidence Validation**.

---

## 📹 Video Demo

> 🎬 **Demo Video (3 Minutes or Less)**: [Insert Your YouTube / Loom Video Link Here]

The demo video showcases:
1. **Live PDF Ingestion** via the Web UI / REST API (`/api/upload`) with incremental fact extraction and cross-document graph linking.
2. **Case 1 (Corroboration)**: Delhivery FY24 express parcel shipment volume (740M) corroborated across Annual Report (p. 36) and Q4 Presentation (p. 6).
3. **Case 2 (Contradiction)**: India's FY25 real GDP growth discrepancy (6.4% Economic Survey vs 6.5% RBI/IMF) with zero forced averaging.
4. **Case 3 (Contextual Reconciliation)**: Fiscal deficit variance explained by reporting scope differences (RBI 4.7% Gross Fiscal Deficit vs IMF 4.9% Central Govt Deficit target).
5. **Case 4 (Uncertainty Handling)**: Table cell ambiguity (`81,417.43` missing unit context) explicitly tagged as `UNCERTAIN`.

---

## 🚀 Setup and Run Instructions

### Prerequisites
- Python 3.10 or higher
- Modern Web Browser (Chrome, Edge, Firefox, Safari)

### 1. Installation
Clone the repository and install the lightweight Python dependencies:
```bash
git clone https://github.com/your-repo/superjoin2.git
cd superjoin2
pip install -r requirements.txt
```

### 2. Launch the Web Application & REST API
Run the FastAPI application server:
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Open your browser and navigate to:
```
http://localhost:8000
```

### 3. Run the Interactive 4-Case Evaluation CLI Demo
Run all 4 core assignment demo cases with verification telemetry in a single terminal command:
```bash
python run_demo.py
```

### 4. Execute Automated Unit & Integration Tests
Execute the complete test suite (**25 automated unit & integration tests** covering multi-modal parsing, hybrid retrieval, confidence scoring, RAG cases, incremental linking, evidence validation, and REST API endpoints):
```bash
python -m unittest discover tests/ -v
```

---

## 🧠 Approach

### 🏛 System Architecture

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
  [1,200 links]        [145 links]          [4,534 links]
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

### 🔑 Key Engineering Decisions & AI Tools Used

1. **Why Not Just Vector RAG?**
   - Traditional vector embeddings collapse distinct numbers into high-dimensional vector proximity, causing LLMs to average conflicting figures or hallucinate citations.
   - **FKL Solution**: We built a deterministic **FactLinker** that operates on extracted (Subject, Predicate, Canonical Period, Normalized Value) tuples. It explicitly categorizes relationships into `CORROBORATION`, `CONTRADICTION`, and `CONTEXTUAL_DIFFERENCE`.

2. **Deterministic Evidence Validation (Zero Hallucinations)**:
   - Every synthesized RAG response passes through a post-generation **Evidence Validator**.
   - It extracts all numerical claims, percentages, and time periods from the generated response text and verifies them against retrieved source quotes. Any ungrounded metric triggers an `UNSUPPORTED_METRIC_DETECTED` alert and reduces confidence.

3. **100% Offline Capability**:
   - The entire pipeline is functional without external API connectivity, utilizing local BM25 indexing, SQLite relational querying, and deterministic natural language template synthesis.
   - **Optional AI Enhancement**: Google Gemini LLM can be optionally enabled for enhanced linguistic fluency when an API key is present.

4. **Dynamic Schema Evolution & Incremental Linking**:
   - Facts and metric predicates are dynamically extracted without hardcoded database tables or fixed document schemas.
   - New PDFs can be uploaded at runtime via `/api/upload` and incrementally linked into the existing Evidence Graph without needing to re-ingest existing documents.

---

## 🧪 Demonstration of the 4 Required Cases

| Case | Scenario | Query | Ground Truth Ingested | Output & Verification |
| :---: | :--- | :--- | :--- | :--- |
| **Case 1** | **Corroboration** | `"Which sources corroborate Delhivery's FY24 express parcel shipment volume?"` | • Delhivery Annual Report FY24 (p. 36): **740 million parcels**<br>• Delhivery Q4 FY24 Presentation (p. 6): **740 Mn** | ✅ Status: `CORROBORATION`<br>Highlights full agreement on **740M shipments** across both sources with exact page quotes. |
| **Case 2** | **Contradiction** | `"Do the sources agree on India's FY25 real GDP growth?"` | • Economic Survey 2024-25 (p. 1 & 11): **6.4%**<br>• RBI Annual Report 2024-25 (p. 3): **6.5%**<br>• IMF Article IV 2025 (p. 5): **6.5%** | ⚠️ Status: `CONTRADICTION` (6.4% vs 6.5%) & `CORROBORATION` (RBI ↔ IMF 6.5%)<br>Refuses to average or pick one number; presents both conflicting figures with exact source citations. |
| **Case 3** | **Contextual Reconciliation** | `"Why do the fiscal deficit figures differ across the sources?"` | • RBI Annual Report 2024-25 (p. 64): **4.7%** (General Govt GFD)<br>• IMF Article IV 2025 (p. 5): **4.9%** (Central Govt Deficit) | 🔄 Status: `CONTEXTUAL_DIFFERENCE`<br>Explains difference due to distinct reporting definitions and accounting scopes. |
| **Case 4** | **Uncertainty Handling** | `"Can the 81,417.43 revenue value be safely interpreted?"` | • Table cell excerpt: **81,417.43** (ambiguous / missing unit header context) | ❓ Status: `UNCERTAIN`<br>Explicitly refuses to guess whether value represents ₹ crore or ₹ million without explicit evidence. |

---

## ⚠️ Limitations and Next Steps

### Current Limitations
1. **Scanned PDF Support**: Current parser relies on PyMuPDF text and layout table extraction. Scanned image-only PDFs without OCR text layers require an external OCR pre-processor (e.g., Tesseract or PDFocr).
2. **Complex Multi-Page Nested Tables**: Tables spanning across multiple pages with repeated headers require manual table stitching heuristics.
3. **Cross-Lingual Fact Linking**: Fact linking currently standardizes English terms and common financial indicators; multi-lingual cross-document reconciliation (e.g., Hindi to English financial terms) is not yet supported.

### Next Steps & Future Enhancements
- **Vision Language Model (VLM) Parsing Integration**: Integrate layout-aware VLMs (like LayoutLMv3 or Gemini Vision) to extract complex graphical charts and visual infographics.
- **Graph Neural Network (GNN) Discrepancy Detection**: Train graph embedding models on top of SQLite evidence graphs to discover implicit multi-hop contradictions across 100+ documents.
- **Real-Time Streaming Updates**: Implement WebSockets for real-time progress updates during batch ingestion of 50+ large PDF documents.

---

## 📌 Additional Notes

- **Zero API Key Requirement**: To test the platform without an API key, simply run `python run_demo.py` or launch the UI; the system seamlessly defaults to high-accuracy offline deterministic synthesis.
- **Interactive Web Interface**: Includes 5 dedicated tabs:
  1. **💬 Ask Knowledge Base**: Interactive query window with 1-click sample chips, visual confidence badges, evidence audit badges, and expandable source quotes.
  2. **🕸 Evidence Graph**: Interactive force-directed canvas visualizing cross-document connections, corroborations, contradictions, and reconciliations.
  3. **📊 Dashboard**: High-level telemetry, document counts, fact totals, and relationship distributions.
  4. **📄 Documents & Facts**: Searchable and filterable data tables displaying structured facts, normalized numbers, and verbatim evidence snippets.
  5. **🔗 Relationships & Discrepancies**: Dedicated cross-document analysis table with filter tabs for Corroboration, Contradiction, and Contextual Differences.

---

## 📡 REST API Reference

| Method | Endpoint | Description |
| :---: | :--- | :--- |
| `POST` | `/api/upload` | Upload and incrementally ingest a PDF document |
| `POST` | `/api/query` | Contradiction-aware natural language question answering with hybrid retrieval and validation |
| `GET` | `/api/graph` | Retrieve visual evidence graph nodes and edges for UI visualization |
| `GET` | `/api/documents` | List all ingested documents and metadata |
| `GET` | `/api/facts` | Query structured facts with search, type, and document filters |
| `GET` | `/api/relationships` | Retrieve cross-document relationships with verbatim evidence quotes |
| `POST` | `/api/analyze` | Re-run full cross-document correlation analysis |
| `GET` | `/api/failures` | List extraction failures and uncertainty audit logs |
| `GET` | `/api/stats` | System-wide statistics and relationship breakdown |
