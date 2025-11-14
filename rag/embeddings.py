from typing import List
from chromadb.api.types import EmbeddingFunction
from sentence_transformers import SentenceTransformer
from config import EMBED_MODEL_NAME

# Initialize embedding model (loaded once, reused)
embedding_model = SentenceTransformer(EMBED_MODEL_NAME)


# Wraps local sentence-transformers model for ChromaDB & Hugging Face compatibility [https://docs.trychroma.com/docs/embeddings/embedding-functions]
# ChromaDB expects a callable that takes text strings and returns embedding vectors
class LocalEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: List[str]) -> List[List[float]]:
        # 1. Encode text strings to embeddings using local model
        embeddings = embedding_model.encode(
            input,
            show_progress_bar=False,
            convert_to_numpy=True
        )
        # 2. Convert numpy array to list format for ChromaDB
        if hasattr(embeddings, 'tolist'):
            return embeddings.tolist()
        return embeddings