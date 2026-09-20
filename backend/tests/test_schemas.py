import pytest
from pydantic import ValidationError
from backend.app.schemas.sensor_reading import SensorReadingCreate
from backend.app.schemas.device import DeviceCreate

def test_valid_sensor_reading():
    reading = SensorReadingCreate(
        device_id="DIGESTER_001",
        temperature_c=36.0,
        ph=7.2,
        pressure_bar=1.2,
        gas_flow_m3_day=4.5,
        biogas_production_m3_day=4.5,
        source="synthetic"
    )
    assert reading.temperature_c == 36.0
    assert reading.ph == 7.2
    assert reading.source == "synthetic"

def test_invalid_temperature_fails():
    with pytest.raises(ValidationError):
        SensorReadingCreate(
            device_id="DIGESTER_001",
            temperature_c=120.0 # Above physical 70C boundary
        )

def test_invalid_ph_fails():
    with pytest.raises(ValidationError):
        SensorReadingCreate(
            device_id="DIGESTER_001",
            ph=16.0 # Above 14 pH boundary
        )

def test_null_sensor_fields_allowed():
    reading = SensorReadingCreate(
        device_id="DIGESTER_001",
        temperature_c=None,
        ph=None,
        pressure_bar=None
    )
    assert reading.temperature_c is None
    assert reading.ph is None
