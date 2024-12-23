import pandas as pd
import numpy as np
from openai import OpenAI
from sentence_transformers import util, SentenceTransformer
import torch
import time
from datetime import datetime
import textwrap
import json

class EmbeddingLoader:
    def __init__(self, embeddings_file_path=None, enhanced_json_path=None, cached_data=None):
        """
        Initialize the EmbeddingLoader with paths or cached data.

        Args:
            embeddings_file_path (str, optional): Path to the embeddings CSV file.
            enhanced_json_path (str, optional): Path to the enhanced JSON file.
            cached_data (dict, optional): Preloaded embeddings and pages/chunks.
        """
        self.embedding_model = SentenceTransformer(
            model_name_or_path='BAAI/bge-m3',
            device='cpu'
        )
        self.document_summary = None
        self.page_summaries = None

        if cached_data:
            self.pages_and_chunks, self.embeddings = cached_data
        else:
            self.embeddings_file_path = embeddings_file_path
            self.enhanced_json_path = enhanced_json_path
            self.pages_and_chunks, self.embeddings = self._load_embeddings()
            if enhanced_json_path:
                self.document_summary, self.page_summaries = self._load_enhanced_json()

    def _load_embeddings(self):
        """Load and process the embeddings CSV file."""
        print(f"Loading embeddings from: {self.embeddings_file_path}")
        try:
            # Load the CSV file
            df = pd.read_csv(self.embeddings_file_path)
            print("Embedding file loaded")

            # Convert stringified embeddings to numpy arrays
            df['embedding'] = df['embedding'].apply(lambda x: np.array(json.loads(x), dtype=np.float64))
            
            # Combine all embeddings into a single numpy array
            embeddings = np.vstack(df['embedding'].to_numpy())
            
            # Convert to list of dicts for pages and chunks
            pages_and_chunks = df.to_dict(orient="records")
            
            # Debug info
            # print("DataFrame columns:", df.columns)
            # print("\nFirst few rows of the DataFrame:")
            # print(df.head())
            
            return pages_and_chunks, embeddings  # `embeddings` is now a single numpy array
            
        except Exception as e:
            raise Exception(f"Failed to load embeddings: {str(e)}")


    def _load_enhanced_json(self):
        """Load and process the enhanced JSON file if provided."""
        try:
            with open(self.enhanced_json_path, 'r') as file:
                enhanced_data = json.load(file)
            # Print a sample of the enhanced data
            # print(f"Enhanced data sample: {enhanced_data}")
            return (
                enhanced_data.get('document_summary', 'No document summary available.'),
                {int(page): data['summary'] for page, data in enhanced_data.get('pages', {}).items()}
            )
        except Exception as e:
            print(f"Warning: Failed to load enhanced JSON: {str(e)}")
            return None, None

    def retrieve_relevant_resources(self, query: str, n_resources_to_return: int = 4):
        """Embeds a query and returns top k scores and indices from embeddings."""
        print(f"Retrieving relevant resources for query: {query}")
        query_embedding = self.embedding_model.encode(query, convert_to_tensor=False)
        
        # Convert query embedding directly to a numpy array before tensor creation
        query_tensor = torch.tensor(np.array([query_embedding], dtype=np.float64), dtype=torch.float64).to('cpu')
        # print(f"Query tensor: {query_tensor}")

        # Convert embeddings to tensor
        embeddings_tensor = torch.tensor(self.embeddings, dtype=torch.float64).to('cpu')
        # print(f"Embeddings tensor: {embeddings_tensor}")
        # Calculate dot scores
        dot_scores = util.dot_score(query_tensor, embeddings_tensor)[0]
        print(f"Dot scores: {dot_scores}")
        # Return top scores and indices
        return torch.topk(input=dot_scores, k=n_resources_to_return)



    def print_top_results_and_scores(self, query: str, n_resources_to_return: int = 5):
        """Retrieves and prints most relevant resources."""
        print(f"Printing top results and scores for query: {query}")
        scores, indices = self.retrieve_relevant_resources(
            query=query,
            n_resources_to_return=n_resources_to_return
        )
        
        for i, (score, index) in enumerate(zip(scores, indices)):
            chunk = self.pages_and_chunks[index]
            chunk_text = chunk.get("content", "Chunk not found")
            print(f"\nResult {i+1}: Score: {score:.4f}, Page: {chunk.get('page', 'Unknown')}")
            print(textwrap.fill(chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text))
            
        return scores, indices

    def format_prompt(self, query: str, context_items: list[dict]) -> str:
        """Formats the prompt with context and query."""
        formatted_context = f"Document Summary: {self.document_summary}\n\n" if self.document_summary else ""
        
        for item in context_items:
            page_number = item.get('page', 'Unknown')
            page_summary = self.page_summaries.get(page_number, '') if self.page_summaries else ''
            if page_summary:
                print(f"Page {page_number}: {page_summary}")
                formatted_context += f"Page {page_number}: {page_summary}\n\n"
            formatted_context += f"Content from page {page_number}: {item.get('content', '')}\n\n"

        return f"""Use the following context to answer the user query:

{formatted_context}

User query: {query}
Answer:"""

def generate_bot_response(message, chat_history, embeddings_loader, client, system_prompt):
    """Generate a response using the embedding loader and OpenAI."""
    # print(f"Generating bot response for message: {message}")
    scores, indices = embeddings_loader.print_top_results_and_scores(query=message)
    context_items = [embeddings_loader.pages_and_chunks[i] for i in indices]
    prompt = embeddings_loader.format_prompt(query=message, context_items=context_items)
    
    bot_message = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": f"{system_prompt} {prompt}"}],
        temperature=1,
        max_tokens=512,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )
    
    response = bot_message.choices[0].message.content
    # print(f"Bot message: {response}")
    chat_history.append((message, response))
    time.sleep(2)
    return response, chat_history

