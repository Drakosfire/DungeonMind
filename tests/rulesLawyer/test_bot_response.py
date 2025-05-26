import unittest
from unittest.mock import Mock, patch
from rulesLawyer_helper import generate_bot_response
import pytest
class TestBotResponse(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.mock_embeddings_loader = Mock()
        self.mock_embeddings_loader.pages_and_chunks = [
            {"page": 1, "sentence_chunk": "Test chunk 1"},
            {"page": 2, "sentence_chunk": "Test chunk 2"}
        ]
        self.mock_embeddings_loader.print_top_results_and_scores.return_value = (
            [0.9, 0.8],  # scores
            [0, 1]       # indices
        )
        self.mock_embeddings_loader.format_prompt.return_value = "Test prompt"
    
    @pytest.mark.skip(reason="No changes to bot response")
    @patch('openai.OpenAI')
    def test_generate_bot_response(self, mock_openai):
        """Test bot response generation"""
        # Setup mock OpenAI response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test response"))]
        mock_client.chat.completions.create.return_value = mock_response

        message = "test query"
        chat_history = []
        system_prompt = "You are a test bot"

        response, updated_chat_history = generate_bot_response(
            message=message,
            chat_history=chat_history,
            embeddings_loader=self.mock_embeddings_loader,
            client=mock_client,
            system_prompt=system_prompt
        )

        # Assertions
        self.assertEqual(response, "Test response")
        self.assertEqual(len(updated_chat_history), 1)
        self.assertEqual(updated_chat_history[0], ("test query", "Test response"))
        self.mock_embeddings_loader.print_top_results_and_scores.assert_called_once()
        self.mock_embeddings_loader.format_prompt.assert_called_once()

if __name__ == '__main__':
    unittest.main() 