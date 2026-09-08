from backend.database import get_db, get_all_documents
from backend.retrieval.hybrid_retriever import HybridRetriever

hr = HybridRetriever()
res = hr.retrieve("What sources report Delhivery's FY24 express parcel shipments?", top_k=10)

print(f"Retrieved {len(res.facts)} facts:")
for f in res.facts[:5]:
    print(f"  [{f.retrieval_source}] {f.document_filename} (p.{f.source_page}): {f.subject} | {f.predicate} = {f.value} {f.unit} ({f.time_period}) score={f.retrieval_score:.2f}")

print(f"\nRetrieved {len(res.relationships)} relationships:")
for r in res.relationships[:3]:
    print(f"  [{r.get('relationship_type')}] {r.get('category')} | {r.get('reasoning')[:120]}")
