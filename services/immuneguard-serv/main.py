"""
ImmuneGuard Service — Score A: Privacy Risk Assessment
=======================================================
Microservice for dataset privacy vulnerability scoring.

Features:
- Dynamic analysis profile generation from user column mappings
- Score A computation (Succ + Vuln)
- XAI-powered human-readable explanations
- MongoDB persistence for analysis profiles and score results
"""
import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.database.mongodb import db
from backend.api.analysis_profile_store_routes import router as analysis_profile_store_router
from backend.api.analysis_profile_store_routes import router_plural as analysis_profiles_router
from backend.api.analysis_profile_routes import router as analysis_profile_router
from backend.api.signal_scanner_routes import (
    initialize_signal_scanner_service,
    router as signal_scanner_router,
)
from backend.api.score_routes import router as score_router
from backend.api.score_routes import router_plural as scores_router
from backend.api.score_routes import score_i_router
from backend.api.score_routes import risk_router
from backend.api.score_routes import stats_router
from core.risk_analysis import initialize_risk_references

# ====================================================================
# FASTAPI APP
# ====================================================================

app = FastAPI(
    title="ImmuneGuard Service",
    description="Score A — Privacy Contamination Risk Assessment with XAI",
    version="1.0.0",
)

@app.middleware("http")
async def set_root_path(request: Request, call_next):
    root_path = request.headers.get("x-forwarded-prefix")
    if root_path:
        request.scope["root_path"] = root_path
    response = await call_next(request)
    return response

# CORS
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:8000,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# ====================================================================
# ROUTERS INCLUSION
# ====================================================================

app.include_router(analysis_profile_store_router)
app.include_router(analysis_profiles_router)
app.include_router(analysis_profile_router)
app.include_router(signal_scanner_router)
app.include_router(score_router)
app.include_router(scores_router)
app.include_router(score_i_router)
app.include_router(risk_router)
app.include_router(stats_router)


# ====================================================================
# ROOT ENDPOINTS
# ====================================================================

@app.get("/")
async def root():
    count = 0
    if db is not None:
        count = await db.immuneguard_scores.count_documents({})
    return {
        "service": "ImmuneGuard Service",
        "status": "running",
        "db_connected": db is not None,
        "total_evaluations": count,
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    try:
        initialize_signal_scanner_service()
        initialize_risk_references()
    except FileNotFoundError:
        # Delay hard failure until endpoint usage so the rest of the service stays available.
        pass


# ====================================================================
# ENTRYPOINT
# ====================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🛡️  IMMUNEGUARD SERVICE (Clean Architecture)")
    print("=" * 60)
    uvicorn.run("main:app", host="0.0.0.0", port=8010, reload=True)
