from app.database import async_session
from app.models import Message, ToolCall, Fact
from sqlalchemy import insert, update


class PostgresMemory:
    async def upsert_tool_call(self, session_id: str, tool_call: dict, output: any):
        async with async_session() as session:
            stmt = insert(ToolCall).values(
                session_id=session_id,
                tool_name=tool_call.get("name", "unknown"),
                arguments=tool_call.get("args", {}),
                result=str(output)
            )
            await session.execute(stmt)
            await session.commit()

    async def upsert_response(self, session_id: str, response: str):
        async with async_session() as session:
            stmt = insert(Message).values(
                session_id=session_id,
                role="assistant",
                content=response
            )
            await session.execute(stmt)
            await session.commit()

    async def save_user_message(self, session_id: str, message: str):
        async with async_session() as session:
            stmt = insert(Message).values(
                session_id=session_id,
                role="user",
                content=message
            )
            await session.execute(stmt)
            await session.commit()

    async def get_session_history(self, session_id: str, limit: int = 50):
        async with async_session() as session:
            from sqlalchemy import select
            stmt = select(Message).where(Message.session_id == session_id).order_by(Message.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [{"role": m.role, "content": m.content} for m in reversed(messages)]

    async def save_fact(self, session_id: str, fact: str, embedding_id: str = None):
        async with async_session() as session:
            stmt = insert(Fact).values(
                session_id=session_id,
                fact=fact,
                embedding_id=embedding_id
            )
            await session.execute(stmt)
            await session.commit()
