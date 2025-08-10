import uvicorn
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field
from typing import List, Any, Dict
import requests
import logging
from qdrant_client import QdrantClient, models

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Retrieval Service",
    description="A service to perform hybrid search and re-ranking on a Qdrant collection.",
)

# --- Pydantic Models for API Data Structure ---
class SearchRequest(BaseModel):
    query: str
    collection_name: str
    model: str = "mxbai-embed-large"  # Default embedding model
    top_k: int = 10

class SearchResult(BaseModel):
    id: str
    score: float
    payload: Dict[str, Any]

# --- Service Clients ---
OLLAMA_API_URL = "http://ollama:11434/api/embeddings"
QDRANT_API_URL = "http://qdrant:6333"

qdrant_client = QdrantClient(url=QDRANT_API_URL)

def get_embedding(text: str, model: str) -> List[float]:
    """
    Gets the embedding for a single piece of text from the Ollama API.
    """
    try:
        response = requests.post(OLLAMA_API_URL, json={"model": model, "prompt": text})
        response.raise_for_status()
        return response.json()["embedding"]
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not connect to Ollama API at {OLLAMA_API_URL}: {e}")
        raise HTTPException(status_code=503, detail=f"Ollama service is unavailable: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while getting embedding: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- API Endpoint ---
@app.post("/search", response_model=List[SearchResult])
async def search(request: SearchRequest):
    """
    Receives a query, generates an embedding for it, and performs a search
    on the specified Qdrant collection.
    """
    logger.info(f"Received search request for collection '{request.collection_name}' with query: '{request.query}'")

    # 1. Get the embedding for the user's query
    try:
        query_vector = get_embedding(request.query, request.model)
        logger.info(f"Successfully generated query vector using model '{request.model}'.")
    except HTTPException as e:
        # Pass on HTTPException from the embedding function
        raise e

    # 2. Perform search in Qdrant
    try:
        # This performs a standard vector search.
        #
        # TO ENABLE HYBRID SEARCH:
        # 1. You must have indexed a text field in your Qdrant collection.
        #    Example during collection creation:
        #    client.recreate_collection(
        #        collection_name="my_collection",
        #        vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
        #        payload_schema={"text": models.TextIndexParams(type="text")},
        #    )
        # 2. Use the `query` method instead of `search`.
        #    search_result = qdrant_client.query(
        #        collection_name=request.collection_name,
        #        query_text=request.query,
        #        query_vector=query_vector,
        #        limit=request.top_k
        #    )

        search_result = qdrant_client.search(
            collection_name=request.collection_name,
            query_vector=query_vector,
            limit=request.top_k,
            with_payload=True  # Include the payload in the results
        )

        logger.info(f"Found {len(search_result)} results in Qdrant.")

        # Format the results into the response model
        formatted_results = [
            SearchResult(id=hit.id, score=hit.score, payload=hit.payload)
            for hit in search_result
        ]

        return formatted_results

    except Exception as e:
        # This can happen if the collection does not exist or Qdrant is down.
        logger.error(f"An error occurred during Qdrant search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to search in Qdrant: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
