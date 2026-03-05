# =============================================================================
# FASTAPI APPLICATION
# =============================================================================
# The main FastAPI app that ties everything together.
# This is what runs when you do: python main.py --mode api
#
# It does 3 things:
#   1. Creates the FastAPI app with metadata (title, description, version)
#   2. Adds middleware:
#      - CORS: allows any frontend to call our API (needed for dashboards)
#      - Request logging: logs every request with method, path, response time
#   3. Includes all 6 route modules (simulate, analysis, optimization, etc.)
#
# The /health endpoint is a standard pattern — load balancers and monitoring
# tools hit this to check if the server is alive.
#
# To test: start the server, then visit http://localhost:8000/docs
# FastAPI auto-generates interactive API documentation (Swagger UI).
# =============================================================================

import logging
import time
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# import all 6 route modules — each one adds endpoints to the app
from api.routes import simulate, analysis, optimization, risk, config, pipeline

logger = logging.getLogger("api")

# create the FastAPI app with metadata shown in the Swagger UI docs
app = FastAPI(
    title="Agentic Warehouse Intelligence Platform",
    description="AI-powered warehouse operations analysis and optimization",
    version="1.0.0",
)

# CORS middleware — allows any frontend (React, dashboard, etc.) to call our API
# allow_origins=["*"] means any domain can make requests (fine for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# request logging middleware — runs on every single request
# logs: "POST /warehouse/simulate → 200 (5234.1 ms)"
@app.middleware("http")
async def log_requests(request: Request, call_next) -> Any:
    start = time.perf_counter()
    response = await call_next(request)  # actually process the request
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s → %d (%.1f ms)",
        request.method, request.url.path, response.status_code, elapsed_ms,
    )
    return response

# register all route modules — each one adds its endpoints to the app
app.include_router(simulate.router)       # POST /warehouse/simulate
app.include_router(analysis.router)       # GET  /warehouse/analysis
app.include_router(optimization.router)   # GET  /warehouse/optimization
app.include_router(risk.router)           # GET  /warehouse/risk
app.include_router(config.router)         # GET + POST /warehouse/config
app.include_router(pipeline.router)       # POST /warehouse/full-pipeline

# health check — standard endpoint for monitoring tools and load balancers
@app.get("/health", tags=["health"])
async def health_check() -> Dict[str, str]:
    return {"status": "healthy", "version": "1.0.0"}
