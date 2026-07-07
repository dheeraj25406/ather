# Aether: Cloud-Native AI Agent System - Project Overview

## Introduction

Aether is a production-ready, cloud-native AI agent system designed to perform multi-step reasoning with external tool use and persistent memory across sessions. It enables an LLM (via Ollama) to intelligently utilize external tools such as web search, SQL queries, Python code execution, and REST API calls while maintaining conversation context through multiple memory layers (Redis, PostgreSQL, and Qdrant).

This document provides a comprehensive overview of the project, including what's been implemented, how the system works, and identified issues or incomplete parts that need attention.

## Project Overview

### Technology Stack
- **Framework**: FastAPI (REST API), Uvicorn (async server)
- **LLM**: Ollama with llama3 model
- **Memory Layers**:
  - Redis: Short-term session cache (24h TTL)
  - PostgreSQL: Long-term conversation history & tool calls
  - Qdrant: Vector embeddings for semantic search
- **Database ORM**: SQLAlchemy 2.0 with asyncpg
- **Agent Framework**: LangGraph 0.2.7
- **Python Version**: 3.11
- **Deployment**: Docker, Docker Compose, Kubernetes (EKS)
- **Testing**: pytest with pytest-asyncio

### Directory Structure
```
- app/ - Main application code
  - agent/ - Agent logic, LLM interface, tool registry
  - tools/ - External tools (web_search, sql_executor, python_executor, api_caller, web_crawl)
  - memory/ - Memory layers (Redis, PostgreSQL, Qdrant)
  - api/ - REST API endpoints (session management)
- frontend/ - Interactive chat UI (HTML/CSS/JS)
- k8s/ - Kubernetes manifests
- scripts/ - Database initialization and seeding
- tests/ - pytest test suite
```

## What's Done

### Core Functionality
1. **Agent Loop System**: Multi-stage iterative reasoning loop with conversation history and tool result accumulation.
2. **Tool Registry**: 5 external tools implemented:
   - web_search: DuckDuckGo HTML search with snippet extraction
   - web_crawl: Intelligent content extraction from URLs
   - sql_query: Sandboxed read-only database queries
   - python_exec: Sandboxed Python code execution in Docker containers
   - api_call: HTTP API calls with SSRF protection
3. **LLM Interface**: Integration with Ollama llama3 model with configurable parameters.
4. **Memory System**: Multi-layer architecture for short-term, long-term, and semantic memory.
5. **REST API**: Session management endpoints for creating, querying, and managing conversations.
6. **Frontend**: Basic chat interface with message display and tool call visualization.
7. **Deployment**: Docker Compose setup with all services, and Kubernetes manifests for production deployment.
8. **Testing**: Comprehensive test suite covering basic functionality, API endpoints, agent loops, and tool safety.

### Key Features Implemented
- Async operations throughout the codebase
- Sandboxed tool execution with security measures
- Comprehensive logging and performance tracking
- Health check endpoints for orchestration
- CORS support for frontend integration
- Robust tool call parsing with multiple fallback strategies
- Conversation context retrieval from multiple sources

## How It's Done

### Agent Loop Flow
1. User sends a query → saved to all memory layers
2. LLM receives prompt with available tools, conversation history, and semantic context
3. If LLM outputs tool call JSON, the tool is invoked
4. Results are accumulated and fed back to LLM
5. Loop continues until LLM provides final answer or max iterations reached (default 5)
6. Final response saved to memory

### Tool Invocation
Tools are invoked through a registry system with 7-stage fallback parsing for LLM outputs. Each tool has specific security measures:
- SQL queries: Whitelist-based table access (though enforcement is incomplete)
- Python execution: Docker-based isolation with import restrictions
- API calls: Domain whitelisting and SSRF protection (though whitelist is disabled)
- Web operations: HTML parsing with fallback strategies

### Memory Management
- **Redis**: Short-term cache with TTL, storing last 20 messages
- **PostgreSQL**: Persistent storage of messages, tool calls, and facts
- **Qdrant**: Vector search for semantic context (currently using hash-based pseudo-embeddings)
- Memory handler orchestrates all layers, retrieving context from Redis and Qdrant for each query

### Deployment
- Docker Compose for local development with 6 services (Redis, PostgreSQL, Qdrant, Ollama, model puller, API)
- Kubernetes manifests for production with rolling updates, persistent volumes, and ingress
- Environment-based configuration for all services

## What's Left / Issues to Address

### Critical Security Issues
1. **SQL Query Safety**: The whitelist for allowed tables is defined but never validated. Users can query any table with SELECT statements, posing a significant security risk.
2. **API Domain Whitelist**: The domain whitelist for API calls is commented out, allowing potential SSRF attacks despite other protective measures.
3. **Python Executor Dependencies**: Import error for 'docker' module that may cause runtime failures.

### Incomplete Features
4. **Qdrant Integration**: Currently uses fake hash-based embeddings instead of real vector embeddings, limiting semantic search effectiveness.
5. **Session Persistence**: API session storage uses in-memory dictionaries, lost on restarts; needs database integration.
6. **Frontend JavaScript**: HTML/CSS is complete, but JavaScript event handlers and API integration are missing.
7. **Test Suite**: Some tests reference non-existent methods, and negative test cases are missing.

### Design Concerns
8. **Memory Performance**: PostgreSQL queries lack indexing, potentially causing performance issues with large datasets.
9. **Error Handling**: Inconsistent error recovery across tools; some errors break the agent loop while others are silently handled.
10. **Web Search Fragility**: Relies on hardcoded HTML parsing patterns that may break with website changes.

### Specific User Concerns
- **SQL Queries**: As mentioned, SQL queries may not work correctly due to unenforced table whitelists and potential security issues.
- **API Calls**: Domain restrictions are bypassed, and while basic SSRF protection exists, the whitelist being disabled increases risk.

## Conclusion

Aether represents a sophisticated AI agent system with solid foundational architecture and comprehensive tooling. The core agent loop, tool integration, and multi-layer memory system are well-implemented and functional for demonstration purposes. However, critical security vulnerabilities and incomplete features must be addressed before production deployment. The identified issues, particularly around SQL query safety and API call restrictions, require immediate attention to ensure system reliability and security.

The project demonstrates advanced concepts in AI agent design, async programming, and microservices architecture, making it a valuable learning resource and potential production system once the outstanding issues are resolved.