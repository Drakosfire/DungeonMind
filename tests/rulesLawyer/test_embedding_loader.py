import unittest
import pandas as pd
import numpy as np
import json
import os
from rulesLawyer_helper import EmbeddingLoader
import pytest
class TestEmbeddingLoader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Create test data files"""
        # Create a simple test embeddings CSV
        cls.test_embeddings_path = "test_embeddings.csv"
        
        # Create embeddings as a single numpy array (3 embeddings of size 384)
        embeddings = np.random.rand(3, 384).astype(np.float64)  # 3 rows, 384 columns
        
        test_data = {
            'page': [1, 1, 2],
            'sentence_chunk': [
                'This is test chunk 1',
                'This is test chunk 2',
                'This is test chunk 3'
            ],
            'embedding_str': [json.dumps(emb.tolist()) for emb in embeddings]
        }
        pd.DataFrame(test_data).to_csv(cls.test_embeddings_path, index=False)

        # Create a test enhanced JSON file
        cls.test_json_path = "test_enhanced.json"
        test_json = {
            "document_summary": "Test document summary",
            "pages": {
                "1": {"summary": "Page 1 summary"},
                "2": {"summary": "Page 2 summary"}
            }
        }
        with open(cls.test_json_path, 'w') as f:
            json.dump(test_json, f)

    def setUp(self):
        """Initialize EmbeddingLoader for each test"""
        self.loader = EmbeddingLoader(
            file_path=self.test_embeddings_path,
            enhanced_json_path=self.test_json_path
        )
    @pytest.mark.skip(reason="No changes to embedding loader")
    def test_load_embeddings(self):
        """Test if embeddings are loaded correctly"""
        self.assertIsNotNone(self.loader.embeddings)
        self.assertEqual(len(self.loader.embeddings), 3)
        self.assertEqual(len(self.loader.pages_and_chunks), 3)

    @pytest.mark.skip(reason="No changes to embedding loader")
    def test_load_enhanced_json(self):
        """Test if enhanced JSON is loaded correctly"""
        self.assertEqual(self.loader.document_summary, "Test document summary")
        self.assertEqual(len(self.loader.page_summaries), 2)
        self.assertEqual(self.loader.page_summaries[1], "Page 1 summary")

    @pytest.mark.skip(reason="No changes to embedding loader")
    def test_retrieve_relevant_resources(self):
        """Test if relevant resources are retrieved"""
        scores, indices = self.loader.retrieve_relevant_resources(
            query="test chunk",
            n_resources_to_return=2
        )
        self.assertEqual(len(scores), 2)
        self.assertEqual(len(indices), 2)

    @pytest.mark.skip(reason="No changes to embedding loader")
    def test_format_prompt(self):
        """Test prompt formatting"""
        context_items = [
            {"page": 1, "sentence_chunk": "Test chunk 1"},
            {"page": 2, "sentence_chunk": "Test chunk 2"}
        ]
        prompt = self.loader.format_prompt("test query", context_items)
        self.assertIn("test query", prompt)
        self.assertIn("Test chunk 1", prompt)
        self.assertIn("Page 1 summary", prompt)

    @classmethod
    def tearDownClass(cls):
        """Clean up test files"""
        if os.path.exists(cls.test_embeddings_path):
            os.remove(cls.test_embeddings_path)
        if os.path.exists(cls.test_json_path):
            os.remove(cls.test_json_path)

if __name__ == '__main__':
    unittest.main() 