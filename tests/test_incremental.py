"""
Unit tests for incremental indexing and linking.
"""

import unittest
from backend.fact_linker import FactLinker


class TestIncrementalLinking(unittest.TestCase):

    def test_incremental_linking(self):
        linker = FactLinker()

        existing_facts = [
            {
                "id": "fact_old_1",
                "document_id": "doc_1",
                "subject": "Delhivery",
                "predicate": "revenue",
                "value": "₹4,500 crore",
                "numeric_value": 4500.0,
                "unit": "₹ crore",
                "time_period": "FY24",
                "confidence": 0.85,
                "normalized_subject": "delhivery",
                "normalized_predicate": "revenue",
                "normalized_period": "FY2024",
                "normalized_value": 4500.0,
            }
        ]

        new_facts = [
            {
                "id": "fact_new_1",
                "document_id": "doc_2",
                "subject": "Delhivery",
                "predicate": "revenue",
                "value": "₹4,500 crore",
                "numeric_value": 4500.0,
                "unit": "₹ crore",
                "time_period": "FY24",
                "confidence": 0.9,
                "normalized_subject": "delhivery",
                "normalized_predicate": "revenue",
                "normalized_period": "FY2024",
                "normalized_value": 4500.0,
            }
        ]

        docs = [
            {"id": "doc_1", "filename": "doc1.pdf"},
            {"id": "doc_2", "filename": "doc2.pdf"},
        ]

        new_rels = linker.analyze_incremental(new_facts, existing_facts, docs)
        self.assertEqual(len(new_rels), 1)
        self.assertEqual(new_rels[0].relationship_type, "corroboration")


if __name__ == "__main__":
    unittest.main()
