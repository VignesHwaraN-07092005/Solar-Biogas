from sqlalchemy import Column, String, DateTime, Boolean
from datetime import datetime, timezone
from backend.app.database import Base

class Device(Base):
    __tablename__ = "devices"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    location = Column(String(256), nullable=True)
    status = Column(String(32), default="ONLINE")  # ONLINE, OFFLINE, WARNING
    mode = Column(String(32), default="DEMO")      # DEMO, LIVE
    is_active = Column(Boolean, default=True)
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
