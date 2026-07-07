import pytest
import asyncio
from app.agent.tool_registry import ToolRegistry
from app.agent.tools.web_search import web_search
from app.agent.tools.python_executor import run_python
from app.agent.tools.api_caller import call_api


@pytest.mark.asyncio
async def test_web_search_valid():
    """Test web search with valid query."""
    result = await web_search("Python programming")
    assert isinstance(result, dict)
    assert "query" in result
    assert result["query"] == "Python programming"


@pytest.mark.asyncio
async def test_python_executor_safe():
    """Test safe Python code execution."""
    code = "print('hello world')"
    result = await run_python(code)
    assert result["returncode"] == 0
    assert "hello" in result["stdout"]


@pytest.mark.asyncio
async def test_python_executor_blocked():
    """Test that dangerous code is blocked."""
    code = "import os; os.system('ls')"
    result = await run_python(code)
    assert result["returncode"] == -1
    assert "Security error" in result["stderr"]


@pytest.mark.asyncio
async def test_python_executor_timeout():
    """Test that long-running code times out."""
    code = "import time; time.sleep(60)"
    result = await run_python(code)
    assert result["returncode"] == -1
    assert "timeout" in result["stderr"].lower()


@pytest.mark.asyncio
async def test_api_caller_valid():
    """Test API caller with valid endpoint."""
    result = await call_api(url="https://jsonplaceholder.typicode.com/posts/1")
    assert isinstance(result, dict)
    assert "status_code" in result
    assert result["status_code"] == 200


@pytest.mark.asyncio
async def test_api_caller_localhost_blocked():
    """Test that localhost APIs are blocked."""
    result = await call_api(url="http://localhost:8000/health")
    assert "error" in result or result["status_code"] != 200


@pytest.mark.asyncio
async def test_tool_registry_parsing():
    """Test tool call parsing."""
    registry = ToolRegistry()
    
    # Test valid tool call
    response = 'web_search: {"query": "Python"}'
    tool_call = registry.parse_tool_call(response)
    assert tool_call is not None
    assert tool_call["name"] == "web_search"
    assert tool_call["args"]["query"] == "Python"
    
    # Test invalid tool call
    response = 'invalid_tool: {"arg": "value"}'
    tool_call = registry.parse_tool_call(response)
    assert tool_call is None or tool_call["name"] not in registry.available_tools


@pytest.mark.asyncio
async def test_tool_registry_invoke():
    """Test tool invocation through registry."""
    registry = ToolRegistry()
    
    tool_call = {"name": "web_search", "args": {"query": "test"}}
    result = await registry.invoke(tool_call)
    assert isinstance(result, dict)
    assert "query" in result
