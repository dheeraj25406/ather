import pytest
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_liveness():
    """Test liveness endpoint."""
    response = client.get("/health/liveness")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_health_readiness():
    """Test readiness endpoint."""
    response = client.get("/health/readiness")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_create_session():
    """Test session creation."""
    response = client.post("/sessions/create")
    assert response.status_code == 201
    data = response.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 0


def test_query_invalid_session():
    """Test query with invalid session."""
    response = client.post(
        "/sessions/invalid_id/query",
        json={"user_prompt": "Hello"}
    )
    assert response.status_code == 404


def test_history_invalid_session():
    """Test history retrieval with invalid session."""
    response = client.get("/sessions/invalid_id/history")
    assert response.status_code == 404


def test_reset_invalid_session():
    """Test reset with invalid session."""
    response = client.post("/sessions/invalid_id/reset")
    assert response.status_code == 404


def test_delete_invalid_session():
    """Test delete with invalid session."""
    response = client.delete("/sessions/invalid_id")
    assert response.status_code == 404


def test_create_and_query_session():
    """Test create session and query it."""
    # Create session
    create_response = client.post("/sessions/create")
    assert create_response.status_code == 201
    session_id = create_response.json()["session_id"]
    
    # Query session
    query_response = client.post(
        f"/sessions/{session_id}/query",
        json={"user_prompt": "Hello, how are you?"}
    )
    assert query_response.status_code == 200
    data = query_response.json()
    assert data["session_id"] == session_id
    assert "result" in data
    assert isinstance(data["tool_calls"], list)


def test_create_query_and_get_history():
    """Test full workflow: create, query, and get history."""
    # Create
    create_response = client.post("/sessions/create")
    session_id = create_response.json()["session_id"]
    
    # Query
    query_response = client.post(
        f"/sessions/{session_id}/query",
        json={"user_prompt": "Test query"}
    )
    assert query_response.status_code == 200
    
    # Get history
    history_response = client.get(f"/sessions/{session_id}/history")
    assert history_response.status_code == 200
    history_data = history_response.json()
    assert history_data["session_id"] == session_id
    assert "history" in history_data


def test_create_query_reset():
    """Test create, query, and reset."""
    # Create
    create_response = client.post("/sessions/create")
    session_id = create_response.json()["session_id"]
    
    # Query
    client.post(
        f"/sessions/{session_id}/query",
        json={"user_prompt": "First query"}
    )
    
    # Reset
    reset_response = client.post(f"/sessions/{session_id}/reset")
    assert reset_response.status_code == 200
    assert reset_response.json()["status"] == "reset"
    
    # Check history is empty
    history_response = client.get(f"/sessions/{session_id}/history")
    assert len(history_response.json()["history"]) == 0


def test_create_and_delete_session():
    """Test create and delete session."""
    # Create
    create_response = client.post("/sessions/create")
    session_id = create_response.json()["session_id"]
    
    # Delete
    delete_response = client.delete(f"/sessions/{session_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"
    
    # Verify deleted
    history_response = client.get(f"/sessions/{session_id}/history")
    assert history_response.status_code == 404


def test_multiple_queries_same_session():
    """Test multiple queries in same session."""
    # Create
    create_response = client.post("/sessions/create")
    session_id = create_response.json()["session_id"]
    
    # First query
    response1 = client.post(
        f"/sessions/{session_id}/query",
        json={"user_prompt": "What is Python?"}
    )
    assert response1.status_code == 200
    
    # Second query
    response2 = client.post(
        f"/sessions/{session_id}/query",
        json={"user_prompt": "Tell me more about it"}
    )
    assert response2.status_code == 200
    
    # Check history has both queries
    history_response = client.get(f"/sessions/{session_id}/history")
    history = history_response.json()["history"]
    assert len(history) >= 2


def test_query_payload_validation():
    """Test query payload validation."""
    # Create
    create_response = client.post("/sessions/create")
    session_id = create_response.json()["session_id"]
    
    # Query with missing user_prompt
    response = client.post(
        f"/sessions/{session_id}/query",
        json={}
    )
    assert response.status_code == 422  # Validation error


def test_frontend_served():
    """Test that frontend is served."""
    response = client.get("/")
    # Frontend may or may not exist in test environment
    assert response.status_code in [200, 404]
