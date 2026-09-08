"""
Test the 4 required demo cases on the live Fact Knowledge Layer.
"""

import json
from backend.rag.rag_engine import RAGEngine

rag = RAGEngine()

queries = [
    ("CASE 1 — Corroboration", "What sources report Delhivery's FY24 express parcel shipments?"),
    ("CASE 2 — Contradiction", "Do the sources agree on India's FY25 GDP growth?"),
    ("CASE 3 — Contextual Difference", "Why do the fiscal deficit figures differ?"),
    ("CASE 4 — Uncertainty / Failure", "Interpret the 81,417.43 revenue value."),
]

for title, q in queries:
    print("=" * 70)
    print(f"{title}")
    print(f"Question: {q}")
    print("-" * 70)
    res = rag.query(q)
    print(f"Confidence: {res['confidence']}")
    print(f"Validation Status: {res['validation']['validation_status']}")
    print(f"Facts Found: {len(res['facts_used'])}")
    print(f"Relationships Found: {len(res['relationships'])}")
    print(f"\nAnswer:\n{res['answer']}")
    print("-" * 70)
    if res['relationships']:
        print("Key Relationships:")
        for r in res['relationships'][:3]:
            print(f"  [{r.get('relationship_type').upper()}] {r.get('reasoning')}")
    print("\n")
