"""
API Regression and Integration Tests for FastAPI backend.
"""

import unittest
from fastapi.testclient import TestClient
from backend.main import app


class TestAPIEndpoints(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_stats_endpoint(self):
        resp = self.client.get("/api/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("documents", data)
        self.assertIn("facts", data)
        self.assertIn("relationships", data)

    def test_documents_endpoint(self):
        resp = self.client.get("/api/documents")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_facts_endpoint(self):
        resp = self.client.get("/api/facts")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_relationships_endpoint(self):
        resp = self.client.get("/api/relationships")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_query_endpoint(self):
        payload = {"question": "Do the sources agree on India's FY25 GDP growth?"}
        resp = self.client.post("/api/query", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("answer", data)
        self.assertIn("confidence", data)
        self.assertIn("validation", data)
        self.assertIn("facts_used", data)
        self.assertIn("relationships", data)

    def test_graph_endpoint(self):
        resp = self.client.get("/api/graph")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertIn("stats", data)


if __name__ == "__main__":
    unittest.main()
