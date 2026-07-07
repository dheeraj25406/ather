# Aether

An AI agent you can actually talk to across sessions. Ask it something, and it figures out what tools it needs — web search, database queries, code execution, or external APIs — runs them, and chains the results into a coherent answer. It remembers what you told it last week.

Built with FastAPI, Redis, PostgreSQL, Qdrant, and Ollama (and Azure OpenAI). Runs locally with Docker Compose or on AWS EKS for production.

Aether is very similar to Odeseuys by PewDiePie (but we made it first :P)

---

## What it does

Most LLM demos answer questions in isolation. Aether keeps state. Every session has a memory stack: recent messages live in Redis, older history gets summarized into PostgreSQL, and everything is embedded into Qdrant so the agent can pull relevant context back up when it matters.

The agent loop itself is a straightforward implementation — the LLM sees the user message plus available tools, picks one, runs it, gets the result back, and repeats until it's confident enough to respond. No magic, just iteration.

**The four tools:**

- **Web search** via DuckDuckGo — for anything current
- **SQL runner** — SELECT queries only, against the bundled PostgreSQL instance
- **Python sandbox** — runs arbitrary code with a whitelist of safe imports, 30s timeout
- **HTTP caller** — GET/POST/PUT/DELETE against external APIs, with SSRF protection

---

## Running it locally

You need Docker Desktop and Docker Compose. That's it.

```bash
git clone https://github.com/cruelkratos/aether.git && cd aether
docker-compose up -d --build
docker-compose exec api python scripts/init_db.py
```

Five services come up:

| Service    | Port  | What it is                          |
|------------|-------|--------------------------------------|
| API        | 8000  | FastAPI + Uvicorn                   |
| Ollama     | 11434 | Local LLM (llama2 by default)       |
| PostgreSQL | 5432  | Conversation history                |
| Redis      | 6379  | Short-term session cache            |
| Qdrant     | 6333  | Vector DB for semantic retrieval    |

Open `http://localhost:8000` for the chat UI.

The first time Ollama starts, it pulls the model — give it a minute. You can check progress with:
(Ollama is optional we prefered using Azure OpenAI Api for GPT5)

```bash
docker exec aether-ollama-1 ollama list
```

To stop everything:

```bash
docker-compose down
```

---

## API

Sessions are the core abstraction. Create one, query it, come back later.

```bash
# Start a session
curl -X POST http://localhost:8000/sessions/create

# Ask the agent something
curl -X POST http://localhost:8000/sessions/{SESSION_ID}/query \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "What Python libraries are best for time series forecasting?"}'

# Pull the full conversation history
curl http://localhost:8000/sessions/{SESSION_ID}/history
```

**All endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sessions/create` | Create a new session |
| POST | `/sessions/{id}/query` | Send a message |
| GET | `/sessions/{id}/history` | Get conversation history |
| POST | `/sessions/{id}/reset` | Clear session memory |
| DELETE | `/sessions/{id}` | Delete session |
| GET | `/health/liveness` | Liveness probe |
| GET | `/health/readiness` | Readiness probe |
| GET | `/metrics` | Query counts, success rates, latency |

---

## How memory works

There are three layers, each serving a different purpose:

1. **Redis** — the last 20 messages, with a 24-hour TTL. Fast access for active conversations.
2. **PostgreSQL** — full structured history. Survives restarts, queryable.
3. **Qdrant** — embeddings for every message. When the agent builds context for a new query, it retrieves semantically similar past exchanges regardless of how long ago they happened.

At query time, the agent pulls from all three layers and builds a prompt that includes relevant history. This is how it "remembers" something you mentioned two sessions ago.

---

## Tool reference

**Web search**
```json
{ "tool": "web_search", "query": "OpenAI GPT-5 release date" }
```

**SQL query** (SELECT only, 10s timeout)
```json
{ "tool": "sql_query", "query": "SELECT * FROM sessions ORDER BY created_at DESC LIMIT 5" }
```

**Python execution** (whitelisted imports, 30s timeout, no file I/O)
```json
{ "tool": "python_exec", "code": "import math\nprint(math.factorial(10))" }
```

**HTTP API call** (SSRF-protected, 15s timeout)
```json
{
  "tool": "api_call",
  "url": "https://api.github.com/repos/anthropics/anthropic-sdk-python",
  "method": "GET"
}
```

---

## Running tests

```bash
# Inside Docker (recommended — matches the actual runtime environment)
docker-compose exec api pytest -v

# With coverage report
docker-compose exec api pytest --cov=app --cov-report=html

# On your host machine
pip install -r requirements.txt
PYTHONPATH=. pytest -v
```

Test files:
- `tests/test_basic.py` — health checks and service availability
- `tests/test_api.py` — session lifecycle, query handling
- `tests/test_tools.py` — each tool individually
- `tests/test_agent.py` — agent loop, memory integration, end-to-end flows


View Output samples in the testsuite folder to see how the ai agent behaves

---

## Deploying to AWS EKS

For production, you'll want to swap a few things: Ollama → OpenAI API, local PostgreSQL → RDS, local Redis → ElastiCache. The Kubernetes manifests in `k8s/` are written with this in mind.

**One-time cluster setup:**
```bash
eksctl create cluster --name aether-prod --region us-east-1
```

**Deploy:**
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/postgres-statefulset.yaml
kubectl apply -f k8s/redis-statefulset.yaml
kubectl apply -f k8s/qdrant-deployment.yaml
kubectl apply -f k8s/agent-api-deployment.yaml
kubectl apply -f k8s/ingress.yaml
```

**Check status:**
```bash
kubectl get pods -n aether
kubectl logs -n aether deployment/aether-api
```

What changes in prod vs local:
- LLM: set `OPENAI_API_KEY` and update `llm_interface.py` to point at OpenAI
- PostgreSQL → AWS RDS (update `DATABASE_URL` in secrets)
- Redis → AWS ElastiCache (update `REDIS_URL`)
- Add horizontal pod autoscaling for the API deployment
- Configure SSL/TLS through the ingress

---

## Configuration

All configuration lives in `.env`:

```env
REDIS_URL=redis://redis:6379
DATABASE_URL=postgresql+asyncpg://aether:aether_pass@postgres:5432/aether_db
QDRANT_URL=http://qdrant:6333
OLLAMA_URL=http://ollama:11434
```

To use a larger Ollama model, update the `ollama` service in `docker-compose.yml` and pull the model:
```bash
docker exec aether-ollama-1 ollama pull llama2:13b
```

---

## Adding a new tool

1. Create `app/agent/tools/your_tool.py` with an async function:
   ```python
   async def your_tool(**kwargs) -> dict:
       ...
   ```
2. Register it in `app/agent/tool_registry.py`
3. Add tests in `tests/test_tools.py`

---

## Known limitations

A few things that are intentionally simplified for now:

- **No authentication** — the API is open. Add JWT or API keys before exposing this publicly.
- **Python sandboxing is basic** — subprocess with a timeout and import whitelist. For real isolation, use Firecracker or a separate container per execution.
- **Single Ollama instance** — no load balancing for local LLM inference.
- **Hash-based embeddings** — the current embedding generation is a placeholder. Swap in OpenAI embeddings or a Hugging Face model for meaningful semantic search.
- **In-memory session store** — the session index lives in memory; use PostgreSQL for this in production.

---

