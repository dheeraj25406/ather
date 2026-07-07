import uuid
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from starlette.status import HTTP_201_CREATED
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.api.models import SessionCreateResponse, SessionQueryRequest, SessionResponse
from app.agent.agent_loop import AgentLoop
from app.agent.llm_interface import OllamaLLM
from app.memory.memory_handler import MemoryHandler
from app.database import async_session
from app.models import Session, Message

router = APIRouter()
agent_loop = AgentLoop()
memory = MemoryHandler()

# In-memory session store (for short-term demo; use DB in production)
sessions = {}


# Dependency to get DB session
async def get_db():
    async with async_session() as session:
        yield session


@router.get("/list")
async def list_sessions(db: AsyncSession = Depends(get_db), limit: int = 20, offset: int = 0):
    """Fetch all sessions from Postgres, ordered by most recent.
    
    Also populates the in-memory sessions dict with messages from DB.
    """
    result = await db.execute(
        select(Session)
        .order_by(desc(Session.updated_at))
        .limit(limit)
        .offset(offset)
    )
    sessions_list = result.scalars().all()
    
    # Populate in-memory sessions dict with messages from Postgres
    for s in sessions_list:
        if s.id not in sessions:
            sessions[s.id] = []
        
        # Fetch messages for this session
        msg_result = await db.execute(
            select(Message)
            .where(Message.session_id == s.id)
            .order_by(Message.created_at)
        )
        messages = msg_result.scalars().all()
        
        # Update in-memory dict with messages from DB
        sessions[s.id] = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
    
    return {
        "sessions": [
            {
                "id": s.id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                "metadata": s.session_metadata
            }
            for s in sessions_list
        ],
        "limit": limit,
        "offset": offset
    }


@router.get("/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch a single session by ID from Postgres."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    global sessions
    sessions[session.id] = session
    return {
        "id": session.id,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "metadata": session.session_metadata
    }

# LLM warmup: keep the model loaded in Ollama's memory
async def _warmup_llm():
    try:
        llm = OllamaLLM()
        await llm.generate("hi", max_tokens=1)
    except Exception:
        pass


@router.post("/create", response_model=SessionCreateResponse, status_code=HTTP_201_CREATED)
async def create_session(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Create a new agent session and persist to Postgres."""
    session_id = str(uuid.uuid4())
    sessions[session_id] = []
    
    # Write session to Postgres
    new_session = Session(
        id=session_id,
        session_metadata={"created_via": "api"}
    )
    db.add(new_session)
    await db.commit()
    
    background_tasks.add_task(_warmup_llm)
    return SessionCreateResponse(session_id=session_id)


@router.post("/{session_id}/query", response_model=SessionResponse)
async def query_session(session_id: str, request: SessionQueryRequest, db: AsyncSession = Depends(get_db)):
    """Send a query to the agent and persist to Postgres."""
    if session_id not in sessions:
        print("HELLO LOOK AT ME", session_id)
        for s in sessions:
            print(s)
        raise HTTPException(status_code=404, detail="Session not found")

    # Run agent with session history
    result, tool_history = await agent_loop.run(session_id, request.user_prompt, sessions[session_id])

    # Update session history
    sessions[session_id].append({"role": "user", "content": request.user_prompt})
    sessions[session_id].append({"role": "assistant", "content": result})

    # Persist messages to Postgres
    # db.add(Message(session_id=session_id, role="user", content=request.user_prompt))
    # db.add(Message(session_id=session_id, role="assistant", content=result))
    # await db.commit()

    return SessionResponse(
        session_id=session_id,
        result=result,
        tool_calls=tool_history
    )


@router.get("/{session_id}/history")
async def session_history(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get conversation history for a session from Postgres."""
    # Check if session exists
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Fetch messages from Postgres
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    
    return {
        "session_id": session_id,
        "history": [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
    }


@router.post("/{session_id}/reset")
async def reset_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Reset a session's history and memory."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    sessions[session_id] = []
    await memory.clear_session(session_id)
    
    # Clear messages from Postgres
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(Message).where(Message.session_id == session_id))
    await db.commit()
    
    return {"session_id": session_id, "status": "reset"}


@router.delete("/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    await memory.clear_session(session_id)
    
    # Delete from Postgres
    from sqlalchemy import delete as sql_delete
    await db.execute(sql_delete(Message).where(Message.session_id == session_id))
    await db.execute(sql_delete(Session).where(Session.id == session_id))
    await db.commit()
    
    del sessions[session_id]
    return {"session_id": session_id, "status": "deleted"}
