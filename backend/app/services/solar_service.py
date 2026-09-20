from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.models.solar import SolarMetric
from backend.app.models.alert import Alert
from backend.app.schemas.solar import SolarMetricCreate

def process_solar_metric(db: Session, metric_in: SolarMetricCreate) -> SolarMetric:
    ts = metric_in.timestamp or datetime.now(timezone.utc)
    
    # Calculate power if missing
    p_w = metric_in.solar_power_w
    if p_w is None and metric_in.solar_voltage_v is not None and metric_in.solar_current_a is not None:
        p_w = round(metric_in.solar_voltage_v * metric_in.solar_current_a, 2)
        
    metric = SolarMetric(
        device_id=metric_in.device_id,
        timestamp=ts,
        solar_voltage_v=metric_in.solar_voltage_v,
        solar_current_a=metric_in.solar_current_a,
        solar_power_w=p_w,
        battery_voltage_v=metric_in.battery_voltage_v,
        battery_soc_percent=metric_in.battery_soc_percent,
        system_load_current_ma=metric_in.system_load_current_ma,
        system_load_power_w=metric_in.system_load_power_w,
        solar_status=metric_in.solar_status
    )
    db.add(metric)
    
    # Battery low alert
    if metric_in.battery_soc_percent is not None and metric_in.battery_soc_percent < settings.ALERT_BATTERY_SOC_MIN:
        alert = Alert(
            device_id=metric_in.device_id,
            timestamp=ts,
            severity="WARNING",
            parameter="battery",
            triggered_value=metric_in.battery_soc_percent,
            threshold_limit=settings.ALERT_BATTERY_SOC_MIN,
            message=f"Battery state of charge low ({metric_in.battery_soc_percent:.1f}% < {settings.ALERT_BATTERY_SOC_MIN}%)."
        )
        db.add(alert)
        
    db.commit()
    db.refresh(metric)
    return metric
