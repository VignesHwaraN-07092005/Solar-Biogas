from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.models.alert import Alert
from backend.app.models.sensor_reading import SensorReading

def evaluate_reading_for_alerts(db: Session, reading: SensorReading) -> list[Alert]:
    created_alerts = []
    
    # 1. pH checks
    if reading.ph is not None:
        if reading.ph < settings.ALERT_PH_MIN:
            alert = Alert(
                device_id=reading.device_id,
                timestamp=reading.timestamp or datetime.now(timezone.utc),
                severity="CRITICAL" if reading.ph < 6.2 else "WARNING",
                parameter="ph",
                triggered_value=reading.ph,
                threshold_limit=settings.ALERT_PH_MIN,
                message=f"Low pH detected ({reading.ph:.2f} < {settings.ALERT_PH_MIN}). Risk of digester acidification!"
            )
            db.add(alert)
            created_alerts.append(alert)
        elif reading.ph > settings.ALERT_PH_MAX:
            alert = Alert(
                device_id=reading.device_id,
                timestamp=reading.timestamp or datetime.now(timezone.utc),
                severity="WARNING",
                parameter="ph",
                triggered_value=reading.ph,
                threshold_limit=settings.ALERT_PH_MAX,
                message=f"High pH detected ({reading.ph:.2f} > {settings.ALERT_PH_MAX}). Check ammonia loading."
            )
            db.add(alert)
            created_alerts.append(alert)
            
    # 2. Temperature checks
    if reading.temperature_c is not None:
        if reading.temperature_c < settings.ALERT_TEMP_MIN:
            alert = Alert(
                device_id=reading.device_id,
                timestamp=reading.timestamp or datetime.now(timezone.utc),
                severity="WARNING",
                parameter="temperature",
                triggered_value=reading.temperature_c,
                threshold_limit=settings.ALERT_TEMP_MIN,
                message=f"Slurry temperature low ({reading.temperature_c:.1f} C < {settings.ALERT_TEMP_MIN} C). Microbial kinetics inhibited."
            )
            db.add(alert)
            created_alerts.append(alert)
        elif reading.temperature_c > settings.ALERT_TEMP_MAX:
            alert = Alert(
                device_id=reading.device_id,
                timestamp=reading.timestamp or datetime.now(timezone.utc),
                severity="CRITICAL",
                parameter="temperature",
                triggered_value=reading.temperature_c,
                threshold_limit=settings.ALERT_TEMP_MAX,
                message=f"Slurry temperature high ({reading.temperature_c:.1f} C > {settings.ALERT_TEMP_MAX} C). Risk of thermal kill."
            )
            db.add(alert)
            created_alerts.append(alert)
            
    # 3. Pressure checks
    if reading.pressure_bar is not None:
        if reading.pressure_bar >= settings.ALERT_PRESSURE_MAX:
            alert = Alert(
                device_id=reading.device_id,
                timestamp=reading.timestamp or datetime.now(timezone.utc),
                severity="CRITICAL",
                parameter="pressure",
                triggered_value=reading.pressure_bar,
                threshold_limit=settings.ALERT_PRESSURE_MAX,
                message=f"Overpressure critical ({reading.pressure_bar:.2f} bar >= {settings.ALERT_PRESSURE_MAX} bar). Relief valve activation!"
            )
            db.add(alert)
            created_alerts.append(alert)
        elif reading.pressure_bar >= settings.ALERT_PRESSURE_WARN:
            alert = Alert(
                device_id=reading.device_id,
                timestamp=reading.timestamp or datetime.now(timezone.utc),
                severity="WARNING",
                parameter="pressure",
                triggered_value=reading.pressure_bar,
                threshold_limit=settings.ALERT_PRESSURE_WARN,
                message=f"High gas pressure warning ({reading.pressure_bar:.2f} bar >= {settings.ALERT_PRESSURE_WARN} bar). Approaching safety relief threshold."
            )
            db.add(alert)
            created_alerts.append(alert)
        
    return created_alerts

def classify_telemetry_safety(
    temperature_c: float | None = None,
    ph: float | None = None,
    pressure_bar: float | None = None,
    battery_soc_percent: float | None = None,
    solar_power_w: float | None = None,
    biogas_production_m3_day: float | None = None,
    h2s_ppm: float | None = None,
    methane_percent: float | None = None,
    predicted_energy_kwh: float | None = None,
    is_sensor_connected: bool | None = None
) -> dict:
    """
    Authoritative single source of truth for classifying telemetry against safety thresholds.
    Classifies alerts into 5 structured categories:
    DIGESTER, GAS, SENSOR, ENERGY, SOLAR.
    """
    alerts = []

    # 1. DIGESTER CATEGORY (pH & Temperature)
    ph_status = "NORMAL"
    if ph is not None:
        if ph < settings.ALERT_PH_MIN:
            severity = "CRITICAL" if ph < 6.2 else "WARNING"
            ph_status = severity
            alerts.append({
                "category": "DIGESTER",
                "severity": severity,
                "parameter": "ph",
                "triggered_value": ph,
                "threshold_limit": settings.ALERT_PH_MIN,
                "message": f"Low pH detected ({ph:.2f} < {settings.ALERT_PH_MIN}). Risk of digester acidification!"
            })
        elif ph > settings.ALERT_PH_MAX:
            ph_status = "WARNING"
            alerts.append({
                "category": "DIGESTER",
                "severity": "WARNING",
                "parameter": "ph",
                "triggered_value": ph,
                "threshold_limit": settings.ALERT_PH_MAX,
                "message": f"High pH detected ({ph:.2f} > {settings.ALERT_PH_MAX}). Check ammonia loading."
            })

    temp_status = "NORMAL"
    if temperature_c is not None:
        if temperature_c < settings.ALERT_TEMP_MIN:
            temp_status = "WARNING"
            alerts.append({
                "category": "DIGESTER",
                "severity": "WARNING",
                "parameter": "temperature",
                "triggered_value": temperature_c,
                "threshold_limit": settings.ALERT_TEMP_MIN,
                "message": f"Slurry temperature low ({temperature_c:.1f} C < {settings.ALERT_TEMP_MIN} C). Microbial kinetics inhibited."
            })
        elif temperature_c > settings.ALERT_TEMP_MAX:
            temp_status = "CRITICAL"
            alerts.append({
                "category": "DIGESTER",
                "severity": "CRITICAL",
                "parameter": "temperature",
                "triggered_value": temperature_c,
                "threshold_limit": settings.ALERT_TEMP_MAX,
                "message": f"Slurry temperature high ({temperature_c:.1f} C > {settings.ALERT_TEMP_MAX} C). Risk of thermal kill."
            })

    digester_status = "NORMAL"
    if any(a["category"] == "DIGESTER" and a["severity"] == "CRITICAL" for a in alerts):
        digester_status = "CRITICAL"
    elif any(a["category"] == "DIGESTER" and a["severity"] == "WARNING" for a in alerts):
        digester_status = "WARNING"

    # 2. GAS CATEGORY (Pressure, Biogas Yield, H2S, Methane)
    press_status = "NORMAL"
    if pressure_bar is not None:
        if pressure_bar >= settings.ALERT_PRESSURE_MAX:
            press_status = "CRITICAL"
            alerts.append({
                "category": "GAS",
                "severity": "CRITICAL",
                "parameter": "pressure",
                "triggered_value": pressure_bar,
                "threshold_limit": settings.ALERT_PRESSURE_MAX,
                "message": f"Overpressure critical ({pressure_bar:.2f} bar >= {settings.ALERT_PRESSURE_MAX} bar). Relief valve activation!"
            })
        elif pressure_bar >= settings.ALERT_PRESSURE_WARN:
            press_status = "WARNING"
            alerts.append({
                "category": "GAS",
                "severity": "WARNING",
                "parameter": "pressure",
                "triggered_value": pressure_bar,
                "threshold_limit": settings.ALERT_PRESSURE_WARN,
                "message": f"High gas pressure warning ({pressure_bar:.2f} bar >= {settings.ALERT_PRESSURE_WARN} bar). Approaching safety relief threshold."
            })

    if biogas_production_m3_day is not None and biogas_production_m3_day < settings.ALERT_BIOGAS_MIN:
        alerts.append({
            "category": "GAS",
            "severity": "WARNING",
            "parameter": "biogas_production",
            "triggered_value": biogas_production_m3_day,
            "threshold_limit": settings.ALERT_BIOGAS_MIN,
            "message": f"Low biogas yield ({biogas_production_m3_day:.2f} m3/day < {settings.ALERT_BIOGAS_MIN} m3/day). Check organic loading rate."
        })

    if h2s_ppm is not None and h2s_ppm > settings.ALERT_H2S_MAX:
        alerts.append({
            "category": "GAS",
            "severity": "WARNING",
            "parameter": "h2s",
            "triggered_value": h2s_ppm,
            "threshold_limit": settings.ALERT_H2S_MAX,
            "message": f"Elevated H2S ({h2s_ppm:.1f} ppm > {settings.ALERT_H2S_MAX} ppm). Filter conditioning required before generator intake."
        })

    if methane_percent is not None and methane_percent < settings.ALERT_METHANE_MIN:
        alerts.append({
            "category": "GAS",
            "severity": "WARNING",
            "parameter": "methane",
            "triggered_value": methane_percent,
            "threshold_limit": settings.ALERT_METHANE_MIN,
            "message": f"Low methane concentration ({methane_percent:.1f}% < {settings.ALERT_METHANE_MIN}%). Generator combustion efficiency degraded."
        })

    gas_status = "NORMAL"
    if any(a["category"] == "GAS" and a["severity"] == "CRITICAL" for a in alerts):
        gas_status = "CRITICAL"
    elif any(a["category"] == "GAS" and a["severity"] == "WARNING" for a in alerts):
        gas_status = "WARNING"

    # 3. SENSOR CATEGORY (Device connection)
    sensor_status = "NORMAL"
    if is_sensor_connected is False:
        sensor_status = "WARNING"
        alerts.append({
            "category": "SENSOR",
            "severity": "WARNING",
            "parameter": "sensor_connection",
            "triggered_value": 0.0,
            "threshold_limit": 1.0,
            "message": "IoT sensor telemetry node offline or connection timeout."
        })

    # 4. ENERGY CATEGORY (Electricity potential & demand shortfall)
    energy_status = "NORMAL"
    if predicted_energy_kwh is not None and predicted_energy_kwh < settings.ALERT_ENERGY_POTENTIAL_MIN:
        energy_status = "WARNING"
        alerts.append({
            "category": "ENERGY",
            "severity": "WARNING",
            "parameter": "energy_potential",
            "triggered_value": predicted_energy_kwh,
            "threshold_limit": settings.ALERT_ENERGY_POTENTIAL_MIN,
            "message": f"Low electricity potential predicted ({predicted_energy_kwh:.2f} kWh/day < {settings.ALERT_ENERGY_POTENTIAL_MIN} kWh/day). Community demand shortfall risk."
        })

    # 5. SOLAR CATEGORY (Battery SoC & PV power)
    solar_status = "NORMAL"
    if battery_soc_percent is not None and battery_soc_percent < settings.ALERT_BATTERY_SOC_MIN:
        solar_status = "WARNING"
        alerts.append({
            "category": "SOLAR",
            "severity": "WARNING",
            "parameter": "battery_soc",
            "triggered_value": battery_soc_percent,
            "threshold_limit": settings.ALERT_BATTERY_SOC_MIN,
            "message": f"Low battery state of charge ({battery_soc_percent:.1f}% < {settings.ALERT_BATTERY_SOC_MIN}%). Risk of instrumentation shutdown."
        })

    overall = "NORMAL"
    if any(a["severity"] == "CRITICAL" for a in alerts):
        overall = "CRITICAL"
    elif any(a["severity"] == "WARNING" for a in alerts):
        overall = "WARNING"

    return {
        "status": overall,
        "pressure_status": press_status,
        "ph_status": ph_status,
        "temperature_status": temp_status,
        "digester_status": digester_status,
        "gas_status": gas_status,
        "sensor_status": sensor_status,
        "energy_status": energy_status,
        "solar_status": solar_status,
        "alert_count": len(alerts),
        "alerts": alerts,
        "categories": ["DIGESTER", "GAS", "SENSOR", "ENERGY", "SOLAR"],
        "thresholds": {
            "disclaimer": "Prototype configurable alert threshold; validate against actual equipment/process specifications.",
            "categories": {
                "DIGESTER": {
                    "alert_ph_min": settings.ALERT_PH_MIN,
                    "alert_ph_max": settings.ALERT_PH_MAX,
                    "alert_temp_min": settings.ALERT_TEMP_MIN,
                    "alert_temp_max": settings.ALERT_TEMP_MAX
                },
                "GAS": {
                    "alert_pressure_warn": settings.ALERT_PRESSURE_WARN,
                    "alert_pressure_max": settings.ALERT_PRESSURE_MAX,
                    "alert_biogas_min": settings.ALERT_BIOGAS_MIN,
                    "alert_h2s_max": settings.ALERT_H2S_MAX,
                    "alert_methane_min": settings.ALERT_METHANE_MIN
                },
                "SENSOR": {
                    "device_offline_threshold_minutes": settings.DEVICE_OFFLINE_THRESHOLD_MINUTES
                },
                "ENERGY": {
                    "default_generator_efficiency": settings.DEFAULT_GENERATOR_EFFICIENCY,
                    "methane_lhv_kwh": settings.METHANE_LHV_KWH,
                    "alert_energy_potential_min": settings.ALERT_ENERGY_POTENTIAL_MIN,
                    "community_demand_daily_kwh": settings.COMMUNITY_DEMAND_DAILY_KWH
                },
                "SOLAR": {
                    "alert_battery_soc_min": settings.ALERT_BATTERY_SOC_MIN,
                    "alert_solar_power_min": settings.ALERT_SOLAR_POWER_MIN
                }
            },
            "alert_pressure_warn": settings.ALERT_PRESSURE_WARN,
            "alert_pressure_max": settings.ALERT_PRESSURE_MAX,
            "alert_ph_min": settings.ALERT_PH_MIN,
            "alert_ph_max": settings.ALERT_PH_MAX,
            "alert_temp_min": settings.ALERT_TEMP_MIN,
            "alert_temp_max": settings.ALERT_TEMP_MAX
        }
    }
