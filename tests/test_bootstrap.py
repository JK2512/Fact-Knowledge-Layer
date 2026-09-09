"""
Unit tests for the production database bootstrap mechanism.
"""

import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.bootstrap import find_starter_pdfs, bootstrap_database_if_empty
from backend.database import init_db, get_all_documents, get_stats


class TestProductionBootstrap(unittest.TestCase):
    def setUp(self):
        # Create a temporary database file
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        
        self.patcher = patch("backend.database.DB_PATH", Path(self.temp_db_path))
        self.mock_db_path = self.patcher.start()
        init_db()

    def tearDown(self):
        self.patcher.stop()
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def test_find_starter_pdfs(self):
        pdfs = find_starter_pdfs()
        self.assertGreaterEqual(len(pdfs), 6, "Should discover at least 6 starter PDFs in repository")
        filenames = [p.name for p in pdfs]
        self.assertIn("01-delhivery-prospectus-2022-excerpt.pdf", filenames)
        self.assertIn("01-india-economic-survey-2024-25-excerpt.pdf", filenames)

    def test_bootstrap_on_empty_db_and_subsequent_idempotency(self):
        # Verify initial DB is empty
        docs = get_all_documents()
        self.assertEqual(len(docs), 0, "Database should initially be empty")

        # Mock processing function
        call_history = []

        def mock_process_pdf(filepath: str, filename: str) -> dict:
            call_history.append(filename)
            from backend.models import Document
            from backend.database import insert_document
            doc = Document(filename=filename, title="Test", page_count=10)
            insert_document(doc)
            return {"facts_extracted": 10, "relationships_detected": 5}

        # 1st Startup: Should ingest all starter PDFs
        bootstrapped = bootstrap_database_if_empty(mock_process_pdf)
        self.assertTrue(bootstrapped, "Bootstrap should return True on empty DB")
        self.assertGreaterEqual(len(call_history), 6, "All starter PDFs should be processed")

        docs_after = get_all_documents()
        self.assertGreaterEqual(len(docs_after), 6, "DB should now contain documents")

        # 2nd Startup: Should skip bootstrap completely (idempotent)
        call_history_2nd = []
        bootstrapped_2nd = bootstrap_database_if_empty(
            lambda fp, fn: call_history_2nd.append(fn) or {"facts_extracted": 0}
        )
        self.assertFalse(bootstrapped_2nd, "Bootstrap should return False on non-empty DB")
        self.assertEqual(len(call_history_2nd), 0, "No PDFs should be processed on second startup")


if __name__ == "__main__":
    unittest.main()
