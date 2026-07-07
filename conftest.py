import pytest
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_session_id():
    """Provide a test session ID."""
    return "test_session_12345"


@pytest.fixture
def test_query():
    """Provide a test query."""
    return "What is machine learning?"


@pytest.fixture
def test_tool_call():
    """Provide a test tool call."""
    return {
        "name": "web_search",
        "args": {"query": "machine learning basics"}
    }
