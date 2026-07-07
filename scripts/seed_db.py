import asyncio
from app.database import async_session
from sqlalchemy import text

async def seed():
    async with async_session() as session:
        await session.execute(text("INSERT INTO sessions (id, data) VALUES ('sample-session', '{""test"":""value""}') ON CONFLICT (id) DO NOTHING"))
        await session.commit()
    print("Seed data inserted")

if __name__ == "__main__":
    asyncio.run(seed())
