from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pathlib import Path
from app.api.session_routes import router as session_router
from app.logging_utils import metrics

app = FastAPI(title="Aether AI Agent", version="0.1.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(session_router, prefix="/sessions", tags=["sessions"])

# Serve static frontend files
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="static")


@app.get("/health/liveness")
async def liveness():
    """Liveness probe for Kubernetes."""
    return {"status": "alive"}


@app.get("/health/readiness")
async def readiness():
    """Readiness probe for Kubernetes."""
    return {"status": "ready"}


@app.get("/metrics")
async def get_metrics():
    """Get system metrics for monitoring."""
    return JSONResponse(content=metrics.get_metrics())
