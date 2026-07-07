import json
import redis.asyncio as aioredis
from typing import List, Dict, Any
from app.config import settings


class RedisMemory:
    def __init__(self):
        self.redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        self.max_messages = settings.short_term_history  # default 20
        self.ttl = 86400  # 24 hours

    async def _is_available(self) -> bool:
        """Check if Redis connection is alive."""
        try:
            await self.redis.ping()
            return True
        except Exception:
            return False

    async def get_session(self, session_id: str) -> str:
        """Get the last N messages for a session as a readable string."""
        try:
            key = f"session:{session_id}"
            raw_messages = await self.redis.lrange(key, 0, -1)
            if not raw_messages:
                return ""
            messages = []
            for raw in raw_messages:
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    msg = {"content": raw}
                # Format each message naturally
                role = msg.get("role", "")
                content = msg.get("content", "")
                tool = msg.get("tool", "")
                result = msg.get("result", "")
                if role and content:
                    messages.append(f"{role}: {content}")
                elif tool and result:
                    messages.append(f"[tool:{tool}] {result}")
                elif content:
                    messages.append(content)
                else:
                    messages.append(str(msg))
            return "\n".join(messages[-self.max_messages:])
        except Exception:
            return ""

    async def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get the last N messages as structured dicts."""
        try:
            key = f"session:{session_id}"
            raw_messages = await self.redis.lrange(key, 0, -1)
            messages = []
            for raw in raw_messages:
                try:
                    messages.append(json.loads(raw))
                except (json.JSONDecodeError, TypeError):
                    messages.append({"content": raw})
            return messages[-self.max_messages:]
        except Exception:
            return []

    async def append_message(self, session_id: str, message: dict):
        """Append a message (as JSON) to the session list, trim to max, set TTL."""
        try:
            key = f"session:{session_id}"
            serialized = json.dumps(message, default=str)
            await self.redis.rpush(key, serialized)
            # Trim to keep only the last N messages
            await self.redis.ltrim(key, -self.max_messages, -1)
            await self.redis.expire(key, self.ttl)
        except Exception:
            pass  # Redis down — degrade gracefully, don't crash the agent

    async def clear_session(self, session_id: str):
        """Delete all messages for a session."""
        try:
            await self.redis.delete(f"session:{session_id}")
        except Exception:
            pass
