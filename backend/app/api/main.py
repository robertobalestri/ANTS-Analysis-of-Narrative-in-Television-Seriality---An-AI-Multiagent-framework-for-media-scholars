"""FastAPI application main entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from langchain_core.embeddings import Embeddings
import logging
import os

from app.core.logging import setup_logging
from app.core.config import check_env_or_exit
from app.api.v1 import arcs, progressions, characters, vector, library, episodes, settings

# Setup logging
logger = setup_logging(__name__)

# Validate environment variables
check_env_or_exit()

# Disable uvicorn access log to avoid duplicate logging
logging.getLogger("uvicorn.access").handlers = []

from contextlib import asynccontextmanager
from app.services.library.sync import sync_episode_statuses

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run sync at startup
    import os
    data_dir = os.getenv("DATA_DIR", "data")
    await sync_episode_statuses(base_dir=data_dir)
    yield

# Create FastAPI app
app = FastAPI(title="ANTS API", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(arcs.router)
app.include_router(progressions.router)
app.include_router(characters.router)
app.include_router(vector.router)
app.include_router(library.router)
app.include_router(episodes.router)
app.include_router(settings.router, prefix="/api")


class _HealthCheckEmbeddingModel(Embeddings):
    """Embedding model for health check that returns dummy embeddings."""

    def embed_documents(self, texts):
        return [[0.0] * 1536 for _ in texts]

    def embed_query(self, text):
        return [0.0] * 1536


@app.get("/health")
async def health_check():
    """Health check endpoint that verifies all dependencies."""
    import os
    from sqlalchemy import text
    from sqlmodel import create_engine, SQLModel
    from app.models.narrative import NarrativeArc

    health_status = {
        "status": "healthy",
        "database": "unknown",
        "vector_store": "unknown",
        "llm": "unknown"
    }

    # Check database
    try:
        db_path = os.getenv("DATABASE_NAME", "narrative_storage/narrative.db")
        db_url = f'sqlite:///{db_path}'
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health_status["database"] = "connected"
        engine.dispose()
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check vector store
    try:
        from app.services.ai import VectorStoreService
        vector_service = VectorStoreService()
        collection = vector_service.collection
        collection.get()
        health_status["vector_store"] = "connected"
    except Exception as e:
        health_status["vector_store"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check LLM
    try:
        from app.services.ai import get_llm
        llm = get_llm()
        health_status["llm"] = "connected"
    except Exception as e:
        health_status["llm"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    return health_status


@app.get("/api")
async def root():
    """Root API endpoint."""
    return {"message": "ANTS API", "version": "0.1.0"}

# --- Static File Serving for Production ---
# Resolve the path to the frontend dist folder
frontend_path = os.path.join(os.path.dirname(__file__), "../../../frontend/dist")

if os.path.exists(frontend_path):
    logger.info(f"Serving frontend from: {frontend_path}")
    # Mount the static files
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_path, "assets")), name="assets")
    
    # Catch-all route to serve index.html for SPA routing
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # If the path matches an API route, it will be handled by the routers above.
        # Otherwise, we serve index.html.
        return FileResponse(os.path.join(frontend_path, "index.html"))
else:
    logger.warning(f"Frontend dist folder not found at {frontend_path}. API only mode.")
    @app.get("/")
    async def root_redirect():
        return {"message": "ANTS API", "version": "0.1.0", "frontend": "not_found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)