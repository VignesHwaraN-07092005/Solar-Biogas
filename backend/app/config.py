import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    APP_NAME: str = "Biogas Intelligence Platform"
    APP_ENV: str = "development"
    DEBUG: bool = False
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    
    # Database
    DATABASE_URL: str = "sqlite:///./solar_biogas.db"
    
    # CORS Configuration: comma-separated list of allowed origins.
    # Production default uses explicit origins, never unrestricted wildcard "*".
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000"
    
    # System Mode: DEMO (synthetic/research) or LIVE (hardware)
    SYSTEM_MODE: str = "DEMO"
    
    # DIGESTER (Prototype Configurable Thresholds)
    ALERT_PH_MIN: float = 6.5
    ALERT_PH_MAX: float = 8.2
    ALERT_TEMP_MIN: float = 28.0
    ALERT_TEMP_MAX: float = 42.0

    # GAS
    ALERT_PRESSURE_WARN: float = 1.30
    ALERT_PRESSURE_MAX: float = 1.50
    ALERT_BIOGAS_MIN: float = 0.5       # m3/day low production warning threshold
    ALERT_H2S_MAX: float = 500.0        # ppm prototype alert threshold
    ALERT_METHANE_MIN: float = 50.0     # % CH4 prototype threshold

    # SENSOR
    DEVICE_OFFLINE_THRESHOLD_MINUTES: int = 60

    # ENERGY (Configurable Assumptions)
    DEFAULT_GENERATOR_EFFICIENCY: float = 0.30
    METHANE_LHV_KWH: float = 9.94
    ALERT_ENERGY_POTENTIAL_MIN: float = 1.0  # kWh/day low predicted energy
    COMMUNITY_DEMAND_DAILY_KWH: float = 5.20 # Illustrative prototype community demand

    # SOLAR
    ALERT_BATTERY_SOC_MIN: float = 20.0
    ALERT_SOLAR_POWER_MIN: float = 0.05

    # Conversational AI Assistant
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-flash-lite-latest"

settings = Settings()
