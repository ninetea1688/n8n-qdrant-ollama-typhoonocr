import uvicorn
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field
from typing import List, Any, Dict
import requests
import re
import logging

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Chunker and Embedding Service",
    description="A service to chunk text from OCR output and generate embeddings using Ollama.",
)

# --- Pydantic Models for API Data Structure ---
class InputElement(BaseModel):
    """Represents a single element from the unstructured.io output."""
    type: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ChunkRequest(BaseModel):
    """The request body for the /chunk_and_embed endpoint."""
    elements: List[InputElement]
    model: str = "mxbai-embed-large"  # Default embedding model
    chunk_size: int = 1000
    chunk_overlap: int = 200

class Chunk(BaseModel):
    """Represents a single text chunk with its embedding and metadata."""
    text: str
    embedding: List[float]
    metadata: Dict[str, Any]

# --- Text Splitting Logic ---
def recursive_character_text_splitter(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """
    A simple implementation of a recursive character text splitter.
    Tries to split based on a hierarchy of separators.
    """
    if len(text) <= chunk_size:
        return [text]

    separators = ["\n\n", "\n", " ", ""]

    for sep in separators:
        chunks = text.split(sep)
        if len(chunks) > 1:
            # If splitting by this separator creates chunks, we can process them
            break
    else:
        # If no separator works, just split by size
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    # Combine small chunks and handle overlap
    final_chunks = []
    current_chunk = ""
    for chunk in chunks:
        if len(current_chunk) + len(chunk) + (len(sep) if sep else 0) <= chunk_size:
            current_chunk += chunk + sep
        else:
            final_chunks.append(current_chunk.strip())
            # Create overlap
            overlap_start = max(0, len(current_chunk) - chunk_overlap)
            current_chunk = current_chunk[overlap_start:] + chunk + sep

    if current_chunk:
        final_chunks.append(current_chunk.strip())

    return [c for c in final_chunks if c] # Filter out empty strings

# --- Ollama Embedding Client ---
OLLAMA_API_URL = "http://ollama:11434/api/embeddings"

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
@app.post("/chunk_and_embed", response_model=List[Chunk])
async def chunk_and_embed(request: ChunkRequest):
    """
    Receives a list of text elements, chunks them, generates embeddings for each chunk,
    and returns a list of chunks with their embeddings.
    """
    all_chunks = []
    logger.info(f"Starting chunking and embedding for {len(request.elements)} elements with model '{request.model}'.")

    for element in request.elements:
        # Split the text of the element into smaller chunks
        text_chunks = recursive_character_text_splitter(
            element.text,
            request.chunk_size,
            request.chunk_overlap
        )

        logger.info(f"Element of type '{element.type}' split into {len(text_chunks)} chunks.")

        for i, chunk_text in enumerate(text_chunks):
            # Generate embedding for the chunk
            embedding = get_embedding(chunk_text, request.model)

            # Create a metadata object for the chunk
            chunk_metadata = element.metadata.copy()
            chunk_metadata.update({
                "element_type": element.type,
                "chunk_number": i + 1,
                "total_chunks_in_element": len(text_chunks)
            })

            all_chunks.append(Chunk(
                text=chunk_text,
                embedding=embedding,
                metadata=chunk_metadata
            ))

    logger.info(f"Successfully created {len(all_chunks)} chunks with embeddings.")
    return all_chunks

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
