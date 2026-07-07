from typing import List, Dict, Any
import logging
from .redis_layer import RedisMemory
from .postgres_layer import PostgresMemory
from .qdrant_layer import QdrantMemory

logger = logging.getLogger(__name__)

class MemoryHandler:
    def __init__(self):
        self.redis = RedisMemory()
        self.postgres = PostgresMemory()
        self.qdrant = QdrantMemory()

    async def retrieve(self, session_id: str, history: List[Dict[str, Any]]) -> str:
        """Retrieve relevant context from semantic memory only.
        
        Short-term conversation context is already provided via the in-memory
        history list — Redis/Postgres are used for persistence, not prompt context.
        Only Qdrant semantic search adds non-redundant knowledge here.
        """
        # Only use semantic search for additional context beyond conversation history
        query_text = " ".join([str(msg.get("content", "")) for msg in history[-3:]]) if history else ""
        semantic = await self.qdrant.search(session_id, query_text) if query_text else ""

        if semantic:
            logger.info(f"[Memory {session_id[:8]}] Qdrant returned {len(semantic)} chars of context")
            return f"Related knowledge: {semantic}"

        return ""

    async def save_user_message(self, session_id: str, message: str):
        """Save user message to all memory layers."""
        await self.redis.append_message(session_id, {"role": "user", "content": message})
        await self.postgres.save_user_message(session_id, message)

    async def save_tool_result(self, session_id: str, tool_call: Dict[str, Any], output: Any):
        """Save tool call and result to all memory layers."""
        await self.redis.append_message(session_id, {"tool": tool_call["name"], "result": str(output)[:200]})
        await self.postgres.upsert_tool_call(session_id, tool_call, output)
        # TODO: Update Qdrant with embeddings of tool results

    async def save_final_response(self, session_id: str, response: str):
        """Save final response to all memory layers."""
        await self.redis.append_message(session_id, {"role": "assistant", "content": response[:200]})
        await self.postgres.upsert_response(session_id, response)

    async def clear_session(self, session_id: str):
        """Clear all memory for a session."""
        await self.redis.clear_session(session_id)
