"""
Evidence Relationship Graph.
Logical graph abstraction connecting Facts, Documents, and Cross-Document Relationships.
Operates on the SQLite Fact Knowledge Layer without requiring external graph databases.
"""

import json
from typing import List, Dict, Any, Optional, Set
from backend.database import (
    get_all_facts,
    get_all_relationships,
    get_all_documents,
    get_facts_by_ids,
)


class EvidenceGraph:
    """Logical graph abstraction over structured facts and cross-document relationships."""

    def __init__(self):
        pass

    def build_full_graph(
        self,
        relationship_type: Optional[str] = None,
        document_id: Optional[str] = None,
        limit_nodes: int = 150,
    ) -> Dict[str, Any]:
        """Generate graph representation (nodes and edges) for UI visualization or graph queries."""
        documents = get_all_documents()
        doc_map = {d["id"]: d for d in documents}

        all_rels = get_all_relationships()
        if relationship_type:
            all_rels = [r for r in all_rels if r.get("relationship_type") == relationship_type]

        # Gather relevant fact IDs from relationships
        active_fact_ids: Set[str] = set()
        for rel in all_rels:
            fact_ids = rel.get("fact_ids", [])
            for fid in fact_ids:
                active_fact_ids.add(fid)

        if not active_fact_ids:
            # Fallback to top facts if no relationships
            facts = get_all_facts()[:limit_nodes]
        else:
            facts = get_facts_by_ids(list(active_fact_ids)[:limit_nodes])

        fact_map = {f["id"]: f for f in facts}

        nodes = []
        node_ids = set()

        # Document nodes
        for doc in documents:
            if document_id and doc["id"] != document_id:
                continue
            doc_node_id = f"doc_{doc['id']}"
            if doc_node_id not in node_ids:
                node_ids.add(doc_node_id)
                nodes.append({
                    "id": doc_node_id,
                    "type": "document",
                    "label": doc.get("title", doc.get("filename")),
                    "filename": doc.get("filename"),
                    "page_count": doc.get("page_count", 0),
                    "fact_count": doc.get("fact_count", 0),
                    "color": "#3b82f6",  # Blue
                })

        # Fact nodes
        for f in facts:
            if document_id and f.get("document_id") != document_id:
                continue
            fact_node_id = f["id"]
            if fact_node_id not in node_ids:
                node_ids.add(fact_node_id)
                doc = doc_map.get(f.get("document_id"), {})
                nodes.append({
                    "id": fact_node_id,
                    "type": "fact",
                    "label": f"{f.get('predicate')}: {f.get('value')}",
                    "subject": f.get("subject"),
                    "predicate": f.get("predicate"),
                    "value": f.get("value"),
                    "unit": f.get("unit"),
                    "time_period": f.get("time_period"),
                    "document_name": doc.get("filename", "Unknown"),
                    "source_page": f.get("source_page"),
                    "confidence": f.get("confidence"),
                    "source_text": f.get("source_text", "")[:120],
                    "color": "#10b981" if f.get("fact_type") == "numerical" else "#8b5cf6",
                })

        edges = []
        edge_set = set()

        # Edges between facts based on relationships
        for rel in all_rels:
            fact_ids = rel.get("fact_ids", [])
            rel_type = rel.get("relationship_type", "reconciliation")
            if len(fact_ids) >= 2:
                for i in range(len(fact_ids)):
                    for j in range(i + 1, len(fact_ids)):
                        src = fact_ids[i]
                        tgt = fact_ids[j]
                        if src in node_ids and tgt in node_ids:
                            edge_key = (min(src, tgt), max(src, tgt), rel_type)
                            if edge_key not in edge_set:
                                edge_set.add(edge_key)
                                edges.append({
                                    "id": f"rel_{rel['id']}_{i}_{j}",
                                    "source": src,
                                    "target": tgt,
                                    "type": rel_type,
                                    "label": rel_type.upper(),
                                    "reasoning": rel.get("reasoning", ""),
                                    "confidence": rel.get("confidence", 0.5),
                                    "color": (
                                        "#22c55e" if rel_type == "corroboration"
                                        else "#ef4444" if rel_type == "contradiction"
                                        else "#a855f7"
                                    ),
                                })

        # Edges from Document -> Fact
        for f in facts:
            doc_node_id = f"doc_{f.get('document_id')}"
            fact_node_id = f["id"]
            if doc_node_id in node_ids and fact_node_id in node_ids:
                edges.append({
                    "id": f"contains_{doc_node_id}_{fact_node_id}",
                    "source": doc_node_id,
                    "target": fact_node_id,
                    "type": "contains",
                    "label": "CONTAINS",
                    "reasoning": f"Extracted from page {f.get('source_page')}",
                    "confidence": 1.0,
                    "color": "#64748b",
                })

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "corroborations": sum(1 for e in edges if e.get("type") == "corroboration"),
                "contradictions": sum(1 for e in edges if e.get("type") == "contradiction"),
                "reconciliations": sum(1 for e in edges if e.get("type") == "reconciliation"),
            }
        }

    def get_subgraph_for_facts(self, fact_ids: List[str]) -> Dict[str, Any]:
        """Extract a targeted subgraph centered on specific fact IDs (for RAG explanations)."""
        target_ids = set(fact_ids)
        if not target_ids:
            return {"nodes": [], "edges": []}

        facts = get_facts_by_ids(list(target_ids))
        fact_map = {f["id"]: f for f in facts}
        doc_cache = {d["id"]: d for d in get_all_documents()}

        nodes = []
        for f in facts:
            doc = doc_cache.get(f["document_id"], {})
            nodes.append({
                "id": f["id"],
                "label": f"{doc.get('filename', 'Doc')} (p.{f['source_page']}): {f['predicate']} = {f['value']}",
                "value": f["value"],
                "document": doc.get("filename", "Doc"),
                "page": f["source_page"],
                "evidence": f.get("source_text", ""),
            })

        all_rels = get_all_relationships()
        edges = []
        for rel in all_rels:
            rfids = set(rel.get("fact_ids", []))
            common = rfids & target_ids
            if len(common) >= 2:
                common_list = list(common)
                for i in range(len(common_list)):
                    for j in range(i + 1, len(common_list)):
                        edges.append({
                            "source": common_list[i],
                            "target": common_list[j],
                            "type": rel["relationship_type"],
                            "reasoning": rel["reasoning"],
                            "confidence": rel["confidence"],
                        })

        return {"nodes": nodes, "edges": edges}
