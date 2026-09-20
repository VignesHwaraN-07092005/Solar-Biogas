import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.models.device import Device
from backend.app.models.sensor_reading import SensorReading

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

def test_device_crud(db_session):
    device = Device(
        id="TEST_001",
        name="Test Digester",
        location="Lab 1",
        status="ONLINE",
        mode="DEMO"
    )
    db_session.add(device)
    db_session.commit()
    
    fetched = db_session.query(Device).filter(Device.id == "TEST_001").first()
    assert fetched is not None
    assert fetched.name == "Test Digester"
    assert fetched.status == "ONLINE"

def test_sensor_reading_insertion(db_session):
    device = Device(id="TEST_002", name="Test Digester 2")
    db_session.add(device)
    db_session.commit()
    
    reading = SensorReading(
        device_id="TEST_002",
        temperature_c=35.5,
        ph=7.4,
        pressure_bar=1.12,
        gas_flow_m3_day=3.2,
        biogas_production_m3_day=3.2,
        source="synthetic"
    )
    db_session.add(reading)
    db_session.commit()
    
    saved = db_session.query(SensorReading).filter(SensorReading.device_id == "TEST_002").first()
    assert saved is not None
    assert saved.temperature_c == 35.5
    assert saved.ph == 7.4
    assert saved.source == "synthetic"
