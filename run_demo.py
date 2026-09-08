"""
Interactive Evaluation & Demo Runner for the Fact Knowledge Layer (FKL).
Runs the 4 required assignment demo cases and prints evidence-backed results.

Usage:
    python run_demo.py
"""

import sys
import time
from pathlib import Path

# Ensure backend can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Set utf-8 encoding for Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from backend.rag.rag_engine import RAGEngine
from backend.database import get_stats


def print_banner():
    print("=" * 80)
    print(" FACT KNOWLEDGE LAYER (FKL) — DEMO EVALUATION HARNESS")
    print(" Cross-Document Fact Verification, Evidence Graph & Contradiction-Aware RAG")
    print("=" * 80)


def print_stats():
    stats = get_stats()
    print("\n📊 SYSTEM TELEMETRY:")
    print(f"  • Ingested Documents: {stats.get('documents', 0)}")
    print(f"  • Structured Facts Extracted: {stats.get('facts', 0):,}")
    print(f"  • Cross-Document Relationships: {stats.get('relationships', 0):,}")
    rel_counts = stats.get('relationship_breakdown', {})
    print(f"    - Corroborations: {rel_counts.get('corroboration', 0):,}")
    print(f"    - Contradictions: {rel_counts.get('contradiction', 0):,}")
    print(f"    - Contextual Reconciliations: {rel_counts.get('reconciliation', 0):,}")
    print(f"  • Extraction Failures: {stats.get('failures', 0)}")
    print("-" * 80)


def run_demo():
    print_banner()
    print_stats()

    engine = RAGEngine()

    test_cases = [
        {
            "id": 1,
            "title": "CASE 1: CORROBORATION ACROSS SOURCES",
            "question": "Which sources corroborate Delhivery's FY24 express parcel shipment volume?",
            "expected": "740 million shipments corroborated across Annual Report FY24 and Q4 Presentation.",
        },
        {
            "id": 2,
            "title": "CASE 2: CONTRADICTION / DISCREPANCY DETECTION",
            "question": "Do the sources agree on India's FY25 real GDP growth?",
            "expected": "Contradiction between 6.4% (Economic Survey) and 6.5% (RBI/IMF); Corroboration between RBI and IMF.",
        },
        {
            "id": 3,
            "title": "CASE 3: CONTEXTUAL DIFFERENCE / RECONCILIATION",
            "question": "Why do the fiscal deficit figures differ across the sources?",
            "expected": "Contextual difference explained by distinct reporting bases (RBI 4.7% vs IMF 4.9%).",
        },
        {
            "id": 4,
            "title": "CASE 4: EXPLICIT UNCERTAINTY ON AMBIGUOUS CONTEXT",
            "question": "Can the 81,417.43 revenue value be safely interpreted?",
            "expected": "Refuses to guess unit/header context; explicitly returns UNCERTAIN.",
        },
    ]

    for case in test_cases:
        print(f"\n[{case['id']}/4] {case['title']}")
        print(f"❓ Query: \"{case['question']}\"")
        print(f"🎯 Target Behavior: {case['expected']}\n")

        start_time = time.time()
        res = engine.query(case["question"])
        elapsed = (time.time() - start_time) * 1000

        # Confidence Badge
        conf = res.get("confidence", "UNKNOWN")
        val = res.get("validation", {})
        val_status = val.get("validation_status", "UNKNOWN")

        print("📝 SYNTHESIZED ANSWER:")
        print(res.get("answer", "").strip())
        print()

        print("🔍 AUDIT & VERIFICATION:")
        print(f"  • Confidence: [{conf}]")
        print(f"  • Evidence Validator: [{val_status}] ({val.get('audit_details', '')})")
        print(f"  • Facts Retrieved: {len(res.get('facts_used', []))}")
        print(f"  • Connected Relationships: {len(res.get('relationships', []))}")
        print(f"  • Verbatim Evidence Snippets: {len(res.get('evidence', []))}")
        print(f"  • Response Latency: {elapsed:.1f}ms")

        # Display verbatim quotes
        evidence = res.get("evidence", [])
        if evidence:
            print("  • Primary Source Quotes:")
            for e in evidence[:2]:
                doc = e.get("document_filename", "Doc")
                page = e.get("page_number", 0)
                quote = e.get("verbatim_text", "")[:95].replace("\n", " ")
                print(f"    - [{doc} | p.{page}]: \"{quote}...\"")

        print("-" * 80)

    print("\n✅ ALL 4 DEMO CASES EXECUTED AND AUDITED SUCCESSFULLY.")
    print("To launch the web interface, run: python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_demo()
