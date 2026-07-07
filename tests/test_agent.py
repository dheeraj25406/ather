import pytest
import asyncio
from app.agent.agent_loop import AgentLoop
from app.memory.memory_handler import MemoryHandler


@pytest.mark.asyncio
async def test_agent_loop_creation():
    """Test agent loop initialization."""
    agent = AgentLoop()
    assert agent.tools is not None
    assert agent.llm is not None
    assert agent.memory is not None


@pytest.mark.asyncio
async def test_agent_no_tool_called():
    """Test agent returns response without tool calls."""
    agent = AgentLoop()
    session_id = "test_session_1"
    
    result, tools_used = await agent.run(session_id, "What is 2+2?", [])
    
    # Should get some response
    assert isinstance(result, str)
    assert len(result) > 0
    assert isinstance(tools_used, list)


@pytest.mark.asyncio
async def test_agent_history_building():
    """Test agent builds conversation history."""
    agent = AgentLoop()
    session_id = "test_session_2"
    history = []
    
    # First query
    result1, _ = await agent.run(session_id, "Hello", history.copy())
    assert result1 is not None
    
    # Second query (should have access to first response in context)
    result2, _ = await agent.run(session_id, "What did you say?", history.copy())
    assert result2 is not None


@pytest.mark.asyncio
async def test_prompt_building():
    """Test prompt is well-formed."""
    agent = AgentLoop()
    prompt = agent._build_prompt(
        "test query",
        "some context",
        [{"role": "user", "content": "hello"}]
    )
    
    assert "test query" in prompt
    assert "Available tools" in prompt
    assert len(prompt) > 100


@pytest.mark.asyncio
async def test_memory_handler_integration():
    """Test memory handler with agent."""
    memory = MemoryHandler()
    session_id = "test_session_3"
    
    # Save user message
    await memory.save_user_message(session_id, "Test message")
    
    # Save tool result
    tool_call = {"name": "web_search", "args": {"query": "test"}}
    await memory.save_tool_result(session_id, tool_call, {"result": "test"})
    
    # Save final response
    await memory.save_final_response(session_id, "Final answer")
    
    # Retrieve context
    context = await memory.retrieve(session_id, [])
    assert isinstance(context, str)
