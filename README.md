# Fact Knowledge Layer (FKL)
### Cross-Document Fact Verification, Evidence Relationship Graph & Contradiction-Aware RAG

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-green.svg)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey.svg)](https://sqlite.org/)
[![Status](https://img.shields.io/badge/Tests-25%2F25%20Passed-brightgreen.svg)]()
[![Offline Mode](https://img.shields.io/badge/Offline%20Mode-100%25%20Supported-success.svg)]()

The **Fact Knowledge Layer (FKL)** is an evidence-grounded knowledge intelligence platform designed to extract, normalize, link, and reconcile facts across heterogeneous PDF documents. It replaces non-deterministic vector similarity with deterministic entity-metric relationship linking, an interactive **Evidence Relationship Graph**, **Hybrid Retrieval** (Structured SQL + Lexical BM25), a **Contradiction-Aware RAG Engine**, and **Deterministic Post-Generation Evidence Validation**.

---

## 📹 Video Demo

> 🎬 **Demo Video (3 Minutes or Less)**: [Insert Your YouTube / Loom Video Link Here]

The demo video showcases:
1. **Live PDF Ingestion** via the Web UI & REST API (`/api/upload`) with high-speed text/table parsing, metric normalization, and incremental graph updates without rebuilding existing knowledge.
2. **Case 1 (Corroboration)**: Delhivery FY24 express parcel shipment volume (740M) corroborated across Annual Report (p. 36) and Q4 Presentation (p. 6).
3. **Case 2 (Contradiction)**: India's FY25 real GDP growth discrepancy (6.4% Economic Survey vs 6.5% RBI/IMF) with zero forced averaging or hallucinated resolution.
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
git clone https://github.com/JK2512/Fact-Knowledge-Layer.git
cd Fact-Knowledge-Layer
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

## 🧠 Approach & Architecture

### 🏛 High-Level Data Flow

```
                    ┌──────────────┐
                    │  PDF Upload  │ (Single or batch PDF ingestion)
                    └──────┬───────┘
                           ↓
                  ┌──────────────────┐
                  │ Multi-Modal      │ (PyMuPDF high-speed text + layout table parser)
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

---

## 🔥 Key Features & System Capabilities

### 1. Multi-Modal PDF Document Parsing & Table Extraction
- **PyMuPDF Engine**: Parses text blocks, font sizes, bounding boxes, and table layouts with sub-second execution speeds.
- **Layout Awareness**: Extracts tabular structures, row headers, and column headers to prevent unit ambiguity.
- **Page-Accurate Grounding**: Binds every single extracted statement to its exact page number and verbatim quote.

### 2. Dual-Mode Extraction Engine (Regex + LLM Fallback)
- **Heuristic Engine**: High-speed regular expression matchers for currency patterns (₹, $, Mn, Cr, %), fiscal years (`FY24`, `Q4 FY24`), and operational metrics.
- **LLM Fallback**: When an API key is available, complex unstructured text uses zero-shot extraction.
- **Dynamic Schema Discovery**: No fixed database schemas or hardcoded rules; entity subjects, metric predicates, and values are inferred dynamically.

### 3. Canonical Metric & Time Normalization
- **Currency & Scale Standardizer**: Converts values into standardized base scales (e.g., `₹ 50,765.87 Million` → `50,765,870,000` / `50,765.87 Cr`).
- **Period Standardizer**: Maps variant strings (`FY 2024`, `2023-24`, `Q4 24`) into canonical periods (`FY2024`, `Q4 FY2024`).

### 4. Deterministic Fact Linker & Relationship Semantics
Cross-document facts are evaluated using multi-attribute subject-predicate matching:
- **`CORROBORATION`**: Independent documents report matching values (within a 5% error tolerance).
- **`CONTRADICTION`**: Independent documents report conflicting values for the identical entity, metric predicate, and period without qualification.
- **`CONTEXTUAL_DIFFERENCE` / `RECONCILIATION`**: Figures differ on the surface but are reconciled by distinct reporting horizons (annual vs quarterly), accounting scopes (standalone vs consolidated), or revision cycles.
- **`UNCERTAIN`**: Ambiguous statements lacking unit/header context are explicitly flagged rather than guessed.

### 5. Interactive Force-Directed Evidence Relationship Graph
- Accessible via `/api/graph` and visually interactive in the UI.
- Nodes represent **Document Filings** (Blue) and **Structured Facts** (Green). Edges represent **Corroborations** (Green), **Contradictions** (Red), and **Reconciliations** (Purple).
- Built dynamically on top of SQLite facts without requiring heavy external graph databases like Neo4j.

### 6. Hybrid Retrieval Engine (Structured SQL + Lexical BM25)
- **Structured Relational Filtering**: Queries database by subject entity, metric predicate, canonical period, and fact type.
- **Lexical BM25 Search**: Ranks enriched fact cards against natural-language question tokens.
- **Reciprocal Rank Fusion (RRF)**: Merges, deduplicates, and re-ranks facts while attaching connected cross-document relationship edges.

### 7. Contradiction-Aware RAG Synthesis Engine
- **Non-Averaging Logic**: When conflicting numbers exist (e.g. GDP 6.4% vs 6.5%), the engine preserves both values with source evidence rather than guessing or averaging.
- **100% Offline Deterministic Synthesis**: Default rule-based template synthesizer builds structured, evidence-backed answers offline.
- **Optional Gemini LLM Synthesis**: Enhances prose fluency while strictly constrained to the retrieved fact bundle.

### 8. Deterministic Post-Generation Evidence Validator
- Operates after answer generation to ensure zero factual hallucination.
- Extracts all numerical values, percentages, fiscal periods, and document references from the synthesized text.
- Cross-references each token against the retrieved source facts and verbatim quotes.
- Flags ungrounded numbers with `UNSUPPORTED_METRIC_DETECTED` and lowers confidence.

### 9. Incremental Ingestion & Scalability
- Uploading new PDFs via `/api/upload` automatically links new facts with existing knowledge without rebuilding existing database records.
- Handles large PDFs (100+ pages) in seconds.

---

## 📊 Fact Knowledge Layer vs. Traditional Approaches

| Dimension | Traditional Vector RAG | GraphRAG (Neo4j/Vector) | Fact Knowledge Layer (FKL) |
| :--- | :--- | :--- | :--- |
| **Contradiction Detection** | Silent failure: LLM averages numbers or picks one arbitrary source. | Complex graph traversals; often misses numerical discrepancies. | **Deterministic FactLinker** explicitly flags `CONTRADICTION` with source evidence. |
| **Context Reconciliation** | Treats annual vs quarterly differences as errors. | Requires pre-defined ontology schemas. | Detects **Contextual Differences** (reporting scope, period alignment). |
| **Hallucination Prevention** | Relies on LLM prompt instructions ("don't lie"). | Relies on prompt engineering. | **Post-Generation Evidence Validator** scans every metric token. |
| **Source Grounding** | Chunk-level citations (often inaccurate). | Graph node citations. | **Page-accurate verbatim quote & document ID binding**. |
| **Offline Independence** | Requires external LLM API calls. | Requires vector DB + LLM. | **100% Offline execution** supported out-of-the-box. |
| **Infrastructure Overhead** | Vector DB (Pinecone/Weaviate) + LLM API. | Neo4j + Vector DB + LLM. | **Zero-dependency lightweight Python + SQLite**. |

---

## 🧪 Demonstration of the 4 Required Cases

| Case | Scenario | Query | Ground Truth Ingested | Output & Verification |
| :---: | :--- | :--- | :--- | :--- |
| **Case 1** | **Corroboration** | `"Which sources corroborate Delhivery's FY24 express parcel shipment volume?"` | • Delhivery Annual Report FY24 (p. 36): **740 million parcels**<br>• Delhivery Q4 FY24 Presentation (p. 6): **740 Mn** | ✅ Status: `CORROBORATION`<br>Highlights full agreement on **740M shipments** across both sources with exact page quotes. |
| **Case 2** | **Contradiction** | `"Do the sources agree on India's FY25 real GDP growth?"` | • Economic Survey 2024-25 (p. 1 & 11): **6.4%**<br>• RBI Annual Report 2024-25 (p. 3): **6.5%**<br>• IMF Article IV 2025 (p. 5): **6.5%** | ⚠️ Status: `CONTRADICTION` (6.4% vs 6.5%) & `CORROBORATION` (RBI ↔ IMF 6.5%)<br>Refuses to average or pick one number; presents both conflicting figures with exact source citations. |
| **Case 3** | **Contextual Reconciliation** | `"Why do the fiscal deficit figures differ across the sources?"` | • RBI Annual Report 2024-25 (p. 64): **4.7%** (General Govt GFD)<br>• IMF Article IV 2025 (p. 5): **4.9%** (Central Govt Deficit) | 🔄 Status: `CONTEXTUAL_DIFFERENCE`<br>Explains difference due to distinct reporting definitions and accounting scopes. |
| **Case 4** | **Uncertainty Handling** | `"Can the 81,417.43 revenue value be safely interpreted?"` | • Prospectus excerpt: **81,417.43** (ambiguous / missing unit header context) | ❓ Status: `UNCERTAIN`<br>Explicitly refuses to guess whether value represents ₹ crore or ₹ million without explicit evidence. |

---

## 🖥 Interactive Web Interface

The single-page web interface (`http://localhost:8000`) is organized into 5 dedicated views:

1. **💬 Ask Knowledge Base**: Interactive natural language query window with sample query chips, visual confidence badges, evidence audit badges, and expandable source quotes.
2. **🕸 Evidence Graph**: Interactive force-directed canvas visualizing cross-document connections, corroborations, contradictions, and reconciliations.
3. **📊 Dashboard**: High-level telemetry, document counts, fact totals, and relationship distributions.
4. **📄 Documents View**: Ingested document registry showing page counts, fact distributions, and drag-and-drop upload modal.
5. **🔗 Relationships Explorer**: Cross-document analysis table with filter tabs for Corroboration, Contradiction, and Contextual Differences.

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

---

## 🧪 Automated Test Suite (25 Tests)

Run the full automated test suite:
```bash
python -m unittest discover tests/ -v
```

**Test Coverage Highlights**:
- `test_api.py`: Tests all 6 REST API endpoints (`/api/documents`, `/api/facts`, `/api/graph`, `/api/query`, `/api/relationships`, `/api/stats`).
- `test_rag.py`: Verifies the 4 mandatory assignment cases (Corroboration, Contradiction, Reconciliation, Uncertainty).
- `test_confidence.py`: Validates multi-factor confidence scoring algorithms and ambiguity penalties.
- `test_validator.py`: Tests hallucinated metric detection and grounding verification.
- `test_incremental.py`: Verifies incremental PDF ingestion and fact linking.
- `test_retrieval.py`: Verifies SQL, BM25, and reciprocal rank fusion hybrid retrieval.

---

## ⚠️ Limitations and Next Steps

### Current Limitations
1. **Scanned OCR PDFs**: Current parser relies on PyMuPDF text and layout table extraction. Scanned image-only PDFs without OCR text layers require an external OCR pre-processor (e.g., Tesseract).
2. **Multi-Page Nested Tables**: Tables spanning across multiple pages with repeated headers require manual table stitching heuristics.
3. **Cross-Lingual Fact Linking**: Fact linking currently standardizes English terms and common financial indicators.

### Next Steps & Future Enhancements
- **Vision Language Model (VLM) Integration**: Integrate layout-aware VLMs (LayoutLMv3) to extract complex graphical charts and visual infographics.
- **Graph Neural Network (GNN) Discrepancy Detection**: Train graph embedding models on top of SQLite evidence graphs to discover implicit multi-hop contradictions across 100+ documents.
- **Real-Time WebSockets**: Implement real-time progress streaming during batch ingestion of 50+ large PDF documents.

---

## 📌 Additional Notes

- **Zero API Key Requirement**: To test the platform without an API key, run `python run_demo.py` or launch the UI; the system seamlessly defaults to high-accuracy offline deterministic synthesis.
- **Repository Link**: [https://github.com/JK2512/Fact-Knowledge-Layer](https://github.com/JK2512/Fact-Knowledge-Layer)
- **Submission Form**: [Superjoin Submission Form](https://forms.gle/3fLdBQ2D6Zm2Gqtv7)
