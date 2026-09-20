from backend.app.api.health import router as health_router
from backend.app.api.devices import router as devices_router
from backend.app.api.readings import router as readings_router
from backend.app.api.forecast import router as forecast_router
from backend.app.api.models import router as models_router
from backend.app.api.alerts import router as alerts_router
from backend.app.api.solar import router as solar_router
from backend.app.api.chat import router as chat_router
from backend.app.api.simulator import router as simulator_router
from backend.app.api.ingestion import router as ingestion_router
from backend.app.api.energy import router as energy_router

__all__ = [
    "health_router",
    "devices_router",
    "readings_router",
    "forecast_router",
    "models_router",
    "alerts_router",
    "solar_router",
    "chat_router",
    "simulator_router",
    "ingestion_router",
    "energy_router",
]
