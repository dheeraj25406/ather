from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import VectorParams, Distance, PointStruct
from app.config import settings
import hashlib
import json
from typing import List, Dict, Any


class QdrantMemory:
    def __init__(self):
        self.client = QdrantClient(url=settings.qdrant_url)
        self.collection_name = "aether_memory"
        self.vector_size = 384  # Small embedding dimension for fast operations
        self.ensure_collection()
        self.point_id_counter = 0

    def ensure_collection(self):
        """Create collection if it doesn't exist."""
        try:
            self.client.get_collection(self.collection_name)
        except UnexpectedResponse:
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
            )

    def _simple_embedding(self, text: str) -> List[float]:
        """Generate a simple hash-based embedding. Replace with proper embeddings in production."""
        # Create a deterministic embedding from text hash
        text = text.lower()[:512]  # Limit text length
        
        # Use hash to generate reproducible random values
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        
        # Generate vector using pseudo-random sequence
        embedding = []
        for i in range(self.vector_size):
            # Use modulo arithmetic to create deterministic but varied values
            val = (hash_val + i * 12345) % 10000
            embedding.append((val - 5000) / 5000.0)  # Normalize to [-1, 1]
        
        # Normalize L2
        magnitude = sum(x**2 for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]
        
        return embedding

    async def search(self, session_id: str, query: str, limit: int = 3) -> str:
        """Search for relevant memories based on query."""
        if not query or len(query) < 3:
            return ""
        
        try:
            query_vector = self._simple_embedding(query)
            
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter={
                    "must": [
                        {
                            "key": "session_id",
                            "match": {"value": session_id}
                        }
                    ]
                },
                limit=limit,
                score_threshold=0.5
            )
            
            if not results:
                return ""
            
            memories = []
            for result in results:
                if result.payload and "text" in result.payload:
                    memories.append(result.payload["text"])
            
            return "\n".join(memories) if memories else ""
        except Exception:
            return ""

    async def upsert(self, session_id: str, text: str, metadata: Dict[str, Any] = None) -> str:
        """Store a memory in Qdrant."""
        try:
            self.point_id_counter += 1
            point_id = hash((session_id, text, self.point_id_counter)) % 2147483647
            
            embedding = self._simple_embedding(text)
            
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "session_id": session_id,
                    "text": text[:500],  # Truncate for storage
                    "metadata": metadata or {}
                }
            )
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            return str(point_id)
        except Exception as e:
            return f"error_{str(e)}"
