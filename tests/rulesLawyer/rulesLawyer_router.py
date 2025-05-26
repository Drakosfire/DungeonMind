from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
from DungeonMindServer.ruleslawyer.ruleslawyer_helper import EmbeddingLoader, generate_bot_response
from openai import OpenAI

router = APIRouter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for single embedding set
current_embeddings = None
current_pages_and_chunks = None
openai_client = OpenAI()
SYSTEM_PROMPT = """You are a friendly and technical answering system, answering questions with accurate, grounded, descriptive, clear, and specific responses. ALWAYS provide a page number citation. Provide a story example. Avoid extraneous details and focus on direct answers. Use the examples provided as a guide for style and brevity. When responding:

    1. Identify the key point of the query.
    2. Provide a straightforward answer, omitting the thought process.
    3. Avoid additional advice or extended explanations.
    4. Answer in an informative manner, aiding the user's understanding without overwhelming them or quoting the source.
    5. DO NOT SUMMARIZE YOURSELF. DO NOT REPEAT YOURSELF. 
    6. End with page citations, a line break and "What else can I help with?" 

    Example:
    Query: Explain how the player should think about balance and lethality in this game. Explain how the game master should think about balance and lethality?
    Answer: In "Swords & Wizardry: WhiteBox," players and the game master should consider balance and lethality from different perspectives. For players, understanding that this game encourages creativity and flexibility is key. The rules are intentionally streamlined, allowing for a potentially high-risk environment where player decisions significantly impact outcomes. The players should think carefully about their actions and strategy, knowing that the game can be lethal, especially without reliance on intricate rules for safety. Page 33 discusses the possibility of characters dying when their hit points reach zero, although alternative, less harsh rules regarding unconsciousness and recovery are mentioned.

For the game master (referred to as the Referee), balancing the game involves providing fair yet challenging scenarios. The role of the Referee isn't to defeat players but to present interesting and dangerous challenges that enhance the story collaboratively. Page 39 outlines how the Referee and players work together to craft a narrative, with the emphasis on creating engaging and potentially perilous experiences without making it a zero-sum competition. Referees can choose how lethal the game will be, considering their group's preferred play style, including implementing house rules to soften deaths or adjust game balance accordingly.

Pages: 33, 39

Use the context provided to answer the user's query concisely. """

class LoadEmbeddingRequest(BaseModel):
    file_path: str

class QueryRequest(BaseModel):
    message: str
    chat_history: list = []

@router.post("/load-embedding")
async def load_embedding(request: LoadEmbeddingRequest):
    global current_embeddings, current_pages_and_chunks
    file_path = request.file_path
    logger.info(f"Loading embeddings from: {file_path}")

    try:
        loader = EmbeddingLoader(file_path=file_path)
        current_embeddings = loader.embeddings
        current_pages_and_chunks = loader.pages_and_chunks
        return {"message": "Embedding loaded successfully"}
    except Exception as e:
        logger.error(f"Error loading embeddings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load embeddings")

@router.post("/query")
async def query_rules(request: QueryRequest):
    if current_embeddings is None:
        raise HTTPException(status_code=400, detail="No embeddings loaded. Please load embeddings first.")
    
    try:
        response, updated_chat_history = generate_bot_response(
            message=request.message,
            chat_history=request.chat_history,
            embeddings=current_embeddings,
            pages_and_chunks=current_pages_and_chunks,
            client=openai_client,
            system_prompt=SYSTEM_PROMPT
        )
        return {"response": response, "chat_history": updated_chat_history}
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process query")