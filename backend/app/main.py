import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.config import settings
from backend.app.database import init_db
from backend.app.api import (
    health_router,
    devices_router,
    readings_router,
    forecast_router,
    models_router,
    alerts_router,
    solar_router,
    chat_router,
    simulator_router,
    ingestion_router,
    energy_router
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database tables
    init_db()
    yield
    # Shutdown logic if needed

app = FastAPI(
    title=settings.APP_NAME,
    description="""
# Biogas Intelligence Platform
Modular IoT monitoring, next-day biogas forecasting, solar telemetry, and explainable AI decision support for anaerobic digestion systems.
    """,
    version="1.0.0",
    lifespan=lifespan
)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse


# CORS configuration: parses comma-separated origins from settings.CORS_ORIGINS
# Production safe: rejects wildcard '*' unless explicitly configured in development
cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
if not settings.DEBUG and ("*" in cors_origins or len(cors_origins) == 0):
    cors_origins = ["http://localhost:8000", "http://127.0.0.1:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(health_router)
app.include_router(devices_router)
app.include_router(readings_router)
app.include_router(forecast_router)
app.include_router(models_router)
app.include_router(alerts_router)
app.include_router(solar_router)
app.include_router(chat_router)
app.include_router(simulator_router)
app.include_router(ingestion_router)
app.include_router(energy_router)

# Mount frontend public static files
app.mount("/dashboard", StaticFiles(directory="frontend/public", html=True), name="dashboard")

@app.get("/")
def root():
    return RedirectResponse(url="/dashboard")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    favicon_path = os.path.join("frontend", "public", "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/x-icon")
    return Response(content=b"", media_type="image/x-icon")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
