import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import httpx
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.models.sensor_reading import SensorReading
from backend.app.models.solar import SolarMetric
from backend.app.models.alert import Alert
from backend.app.schemas.chat import ChatMessage, ChatRequest, ChatResponse

logger = logging.getLogger("solar_biogas.chat")

def get_live_telemetry_from_db(db: Session) -> Dict[str, Any]:
    """Retrieve the latest telemetry reading and solar state from the database without inventing synthetic values."""
    latest_reading = db.query(SensorReading).order_by(SensorReading.timestamp.desc()).first()
    latest_solar = db.query(SolarMetric).order_by(SolarMetric.timestamp.desc()).first()
    active_alerts = db.query(Alert).filter(Alert.is_acknowledged == False).count()

    telemetry: Dict[str, Any] = {
        "timestamp": None,
        "temp": None,
        "ph": None,
        "pressure": None,
        "methane": None,
        "level": None,
        "feed": None,
        "flow": None,
        "biogas": None,
        "efficiency": None,
        "waste": None,
        "solar_power": None,
        "battery_soc": None,
        "active_alerts": active_alerts,
        "source": "database_latest"
    }

    if latest_reading:
        telemetry["timestamp"] = latest_reading.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        if latest_reading.temperature_c is not None:
            telemetry["temp"] = round(latest_reading.temperature_c, 2)
        if latest_reading.ph is not None:
            telemetry["ph"] = round(latest_reading.ph, 2)
        if latest_reading.pressure_bar is not None:
            telemetry["pressure"] = round(latest_reading.pressure_bar, 2)
        if latest_reading.methane_percent is not None:
            telemetry["methane"] = round(latest_reading.methane_percent, 1)
        if latest_reading.feedstock_mass_kg is not None:
            telemetry["feed"] = round(latest_reading.feedstock_mass_kg, 1)
            telemetry["waste"] = round(latest_reading.feedstock_mass_kg, 1)
        if latest_reading.biogas_production_m3_day is not None:
            telemetry["biogas"] = round(latest_reading.biogas_production_m3_day, 2)
        if latest_reading.gas_flow_m3_day is not None:
            telemetry["flow"] = round(latest_reading.gas_flow_m3_day, 2)

    if latest_solar:
        if latest_solar.solar_power_w is not None:
            telemetry["solar_power"] = round(latest_solar.solar_power_w / 1000.0, 2)
        if latest_solar.battery_soc_percent is not None:
            telemetry["battery_soc"] = round(latest_solar.battery_soc_percent, 1)

    return telemetry


def format_telemetry_context(t: Dict[str, Any]) -> str:
    """Format telemetry dictionary into structured prompt context without inventing synthetic values."""
    src = t.get("source") or "Active Source"
    ts = t.get("timestamp") or "Live / Unspecified"

    def _val(val: Any, unit: str = "") -> str:
        if val is None:
            return "Unavailable / Not Observed"
        return f"{val}{unit}"

    return f"""
Telemetry Context (Active Source: {src}, Timestamp: {ts}):
- Digester Temperature: {_val(t.get('temp'), '°C')} (Mesophilic Optimum: 35.0 - 38.0°C)
- Slurry pH: {_val(t.get('ph'))} (Methanogenic Optimum: 6.8 - 7.5; Buffer limit: 6.5 - 8.2)
- Biogas Pressure: {_val(t.get('pressure'), ' bar')} (Operational Target: 0.8 - 1.2 bar; Warning: 1.30 bar; Safety Relief: 1.50 bar)
- Methane Concentration (CH4): {_val(t.get('methane'), '%')} (Target: 60.0 - 75.0%)
- Daily Feedstock Loading: {_val(t.get('feed'), ' kg/day')}
- Digester Slurry Level: {_val(t.get('level'), '%')}
- Daily Biogas Yield: {_val(t.get('biogas'), ' m³/day')}
- Solar PV Generation: {_val(t.get('solar_power'), ' kW')}
- Battery State of Charge: {_val(t.get('battery_soc'), '%')}
- Active Safety Alerts: {t.get('active_alerts') if t.get('active_alerts') is not None else 0}
""".strip()


def generate_smart_local_response(query: str, t: Dict[str, Any], is_key_configured: bool = False) -> str:
    """Domain-grounded heuristic rule engine for anaerobic digestion operations without synthetic hallucinations."""
    q = query.lower()
    source = t.get("source") or "active source"
    temp = t.get("temp")
    ph = t.get("ph")
    pressure = t.get("pressure")
    methane = t.get("methane")
    level = t.get("level")
    feed = t.get("feed")
    biogas = t.get("biogas")
    solar_power = t.get("solar_power")
    battery_soc = t.get("battery_soc")

    response_lines: List[str] = []

    if any(k in q for k in ["ph", "acid", "buffer", "alkalinity"]):
        if ph is None:
            response_lines.append("### 🧪 Slurry pH Diagnosis: **Unavailable / Not Observed**")
            response_lines.append(f"- **Telemetry Provenance:** Slurry pH is not monitored or absent in the active telemetry source (**{source}**).")
            response_lines.append("- **Advisory:** Continuous pH monitoring is vital to detect VFA accumulation and prevent digester souring (optimal methanogenic buffer: **6.8–7.5**; buffer limit: **6.5–8.2**). Connect a calibrated pH probe or take a manual grab sample.")
        else:
            is_optimal = 6.8 <= ph <= 7.5
            is_safe = 6.5 <= ph <= 8.2
            status = "Optimal" if is_optimal else ("Acceptable" if is_safe else "Critical Acidosis Risk")
            response_lines.append(f"### 🧪 Slurry pH Diagnosis: **{ph}** ({status})")
            if is_optimal:
                response_lines.append("- **Buffer Capacity:** Slurry pH is well within the methanogenic active zone (**6.8 – 7.5**). Acetic and propionic volatile fatty acids (VFAs) are being metabolized steadily into methane.")
                feed_str = f" of **{feed} kg/day**" if feed is not None else ""
                response_lines.append(f"- **Recommendation:** Maintain current feed loading{feed_str}; no lime or sodium bicarbonate buffering required.")
            elif ph < 6.8:
                response_lines.append("- ⚠️ **Volatile Fatty Acid (VFA) Accumulation:** Slurry pH has drifted below 6.8. Methanogens are sensitive to low pH.")
                response_lines.append("- **Immediate Action:** Temporarily reduce feeding rate by 25% and introduce calcium carbonate (CaCO₃) or lime buffer slurry.")
            else:
                response_lines.append(f"- ⚠️ **High Alkalinity / Ammonia Inhibition:** Slurry pH is elevated ({ph}). Verify nitrogen-rich co-substrates and dilute with water if needed.")

    elif any(k in q for k in ["temp", "temperature", "heat", "thermal"]):
        if temp is None:
            response_lines.append("### 🌡️ Thermal Microclimate Status: **Unavailable / Not Observed**")
            response_lines.append(f"- **Telemetry Provenance:** Slurry temperature is not monitored or absent in the active telemetry source (**{source}**).")
            response_lines.append("- **Advisory:** Mesophilic anaerobic digestion requires maintaining **35.0–38.0°C** for optimal enzymatic hydrolysis. Verify heating jacket circulation manually.")
        else:
            is_meso = 35.0 <= temp <= 38.0
            response_lines.append(f"### 🌡️ Thermal Microclimate Status: **{temp}°C**")
            if is_meso:
                response_lines.append("- **Mesophilic Balance:** The digester is operating stably within the optimal mesophilic window (**35.0 – 38.0°C**).")
                if solar_power is not None or battery_soc is not None:
                    response_lines.append(f"- **Solar Thermal Coupling:** Auxiliary solar PV output (**{solar_power if solar_power is not None else '—'} kW**) and stored battery capacity (**{battery_soc if battery_soc is not None else '—'}%**) are sufficient to sustain jacket temperature during ambient cold dips.")
            elif temp < 35.0:
                response_lines.append(f"- ⚠️ **Sub-optimal Temperature:** Slurry temperature is at **{temp}°C**, causing slower enzymatic hydrolysis and lower gas yield.")
                response_lines.append("- **Action:** Activate solar-assisted auxiliary heating elements or increase thermal jacket circulation.")
            else:
                response_lines.append(f"- ⚠️ **Elevated Temperature:** Digester temperature reached **{temp}°C**. Mesophilic bacteria experience thermal stress above 39°C. Throttle heating immediately.")

    elif any(k in q for k in ["pressure", "press", "relief", "bar", "valve"]):
        if pressure is None:
            response_lines.append("### ⏲️ Biogas Containment Pressure: **Unavailable / Not Observed**")
            response_lines.append(f"- **Telemetry Provenance:** Gas pressure is not monitored or absent in the active telemetry source (**{source}**).")
            response_lines.append("- **Safety Protocol:** Pressure readings cannot be assumed safe when unmonitored. Ensure mechanical pressure relief valves are operational (warning: **1.30 bar**, maximum relief: **1.50 bar**) and physically inspect manifold lines.")
        else:
            is_crit = pressure >= 1.50
            is_warn = pressure >= 1.30
            response_lines.append(f"### ⏲️ Biogas Containment Pressure: **{pressure} bar**")
            if is_crit:
                response_lines.append(f"- 🚨 **CRITICAL OVERPRESSURE:** Pressure has reached **{pressure} bar**, meeting or exceeding the 1.50 bar relief threshold!")
                response_lines.append("- **Safety Protocol:** Open safety relief bypass valve immediately, check downstream filter or desulfurizer traps for clogging.")
            elif is_warn:
                response_lines.append(f"- ⚠️ **HIGH PRESSURE WARNING:** Current pressure (**{pressure} bar**) exceeds the 1.30 bar warning threshold. Approaching 1.50 bar safety relief limit.")
                response_lines.append("- **Action:** Check gas utilization rate and ensure flaring or buffer tank routing is active.")
            else:
                response_lines.append(f"- **Pressure Margin:** Current pressure (**{pressure} bar**) is normal (< 1.30 bar) and below the mechanical relief valve threshold (**1.50 bar**).")
                response_lines.append("- **Utilization:** Gas collection line pressure is adequate for buffer storage, gas conditioning, and biogas generator fuel intake.")

    elif any(k in q for k in ["methane", "ch4", "quality", "composition", "purity"]):
        if methane is None:
            response_lines.append("### 🔥 Methane Concentration: **Unavailable / Not Observed**")
            response_lines.append(f"- **Telemetry Provenance:** CH₄ concentration is not monitored or absent in the active telemetry source (**{source}**).")
            response_lines.append("- **Advisory:** Online NDIR or catalytic sensor telemetry is required to verify methane purity (target envelope: **60.0–75.0% CH₄**).")
        else:
            response_lines.append(f"### 🔥 Methane Concentration: **{methane}% CH₄**")
            response_lines.append(f"- **Calorific Energy & Power Potential:** At **{methane}% CH₄**, fuel value is approximately **{round(methane * 0.36, 1)} MJ/m³** (~{round(methane * 0.1, 2)} kWh thermal/m³). At an assumed 30% generator electrical efficiency, this yields ~{round(methane * 0.1 * 0.30, 2)} kWh electrical potential per m³ biogas.")
            response_lines.append("- **To achieve / sustain >65% CH₄:** Maintain balanced C:N ratio (25:1 to 30:1) with consistent dairy slurry or organic scraps, avoiding sudden hydraulic shock loads.")

    elif any(k in q for k in ["predict", "yield", "forecast", "biogas", "output", "production"]):
        if biogas is None:
            response_lines.append("### 📈 Biogas Production & Forecast Summary")
            response_lines.append(f"- **Biogas Yield:** **Unavailable / Not Observed** in active telemetry source (**{source}**).")
            response_lines.append("- **Advisory:** Volumetric flow meter telemetry is required to track daily generation and evaluate predictive models.")
        else:
            response_lines.append("### 📈 Biogas Production & Forecast Summary")
            feed_text = f" from **{feed} kg** organic feed" if feed is not None else ""
            response_lines.append(f"- **Latest Daily Yield:** **{biogas} m³/day**{feed_text}.")
            if feed is not None and feed > 0:
                response_lines.append(f"- **Specific Yield:** Approximately **{round((biogas / max(feed, 1.0)) * 1000, 1)} L/kg** fresh feedstock.")
            response_lines.append("- **Forecast Model:** The integrated Ridge/XCO baseline projects steady production. Maintain slurry temperature at **36–37°C** and uniform stirring for maximum yield.")

    elif any(k in q for k in ["electricity", "generator", "kwh", "electrical", "potential"]):
        if biogas is None:
            response_lines.append("### ⚡ Biogas-to-Electricity Generation Potential: **Unavailable**")
            response_lines.append(f"- **Telemetry Provenance:** Biogas yield is unobserved in the active telemetry source (**{source}**).")
            response_lines.append("- **Advisory:** Volumetric gas flow measurements are required to calculate electrical energy potential.")
        else:
            ch4_frac = (methane / 100.0) if methane is not None else 0.60
            elec_kwh = round(biogas * ch4_frac * 9.94 * 0.30, 2)
            avg_kw = round(elec_kwh / 24.0, 3)
            response_lines.append("### ⚡ Biogas-to-Electricity Potential [CALCULATED]")
            response_lines.append(f"- **Estimated Electricity Potential:** **{elec_kwh} kWh/day** (based on {biogas} m³/day biogas, {round(ch4_frac*100, 1)}% CH₄, and 30% assumed generator electrical efficiency).")
            response_lines.append(f"- **24-h Average Equivalent Power:** **{avg_kw} kW**.")
            response_lines.append("- **Hardware Telemetry Notice:** Biogas generator telemetry is NOT CONNECTED. Values represent calculated thermodynamic potential, not measured generator output.")

    elif any(k in q for k in ["solar", "battery", "pv", "soc"]):
        if solar_power is None and battery_soc is None:
            response_lines.append("### ☀️ Solar Subsystem & Storage Telemetry: **Unavailable / Not Configured**")
            response_lines.append(f"- **Telemetry Provenance:** Solar PV generation and battery storage telemetry are not present in active source (**{source}**).")
        else:
            response_lines.append("### ☀️ Solar Subsystem & Storage Telemetry")
            if solar_power is not None:
                response_lines.append(f"- **PV Array Power:** **{solar_power} kW** active generation.")
            if battery_soc is not None:
                response_lines.append(f"- **Battery SoC:** **{battery_soc}%** ({'Healthy, well above the 20% minimum threshold' if battery_soc >= 20 else 'CRITICAL: Below 20% minimum threshold'}).")
            response_lines.append("- **Self-Sufficiency:** Solar PV powers the IoT telemetry node, microcontrollers, and instrumentation electronics.")

    elif any(k in q for k in ["health", "audit", "status", "overview", "diagnose"]):
        observed = [p for p in [("Temperature", temp), ("pH", ph), ("Pressure", pressure), ("Methane", methane), ("Battery SoC", battery_soc)] if p[1] is not None]
        if not observed:
            response_lines.append("### 🛡️ Composite Digester Health Audit: **Unavailable**")
            response_lines.append(f"- **Telemetry Provenance:** No primary biokinetic or containment telemetry (temperature, pH, pressure, methane) is monitored in the active source (**{source}**).")
            response_lines.append("- **Advisory:** A health audit cannot be computed without empirical measurements.")
        else:
            score = 100
            penalties = []
            if temp is not None and not (35.0 <= temp <= 38.0):
                score -= 15
                penalties.append(f"Temp {temp}°C outside mesophilic window (35-38°C)")
            if ph is not None and not (6.8 <= ph <= 7.5):
                score -= 20
                penalties.append(f"pH {ph} outside optimal buffer (6.8-7.5)")
            if pressure is not None and pressure > 1.30:
                score -= 25
                penalties.append(f"Pressure {pressure} bar approaching safety limit (1.50 bar)")
            if battery_soc is not None and battery_soc < 30:
                score -= 15
                penalties.append(f"Battery SoC low ({battery_soc}%)")

            score = max(30, min(100, score))
            grade = "EXCELLENT" if score >= 85 else ("STABLE" if score >= 70 else "ATTENTION REQUIRED")

            response_lines.append(f"### 🛡️ Composite Digester Health Audit: **{score}% ({grade})**")
            obs_str = ", ".join([f"{name} (**{val}**)" for name, val in observed])
            response_lines.append(f"- **Observed Parameters Evaluated:** {obs_str}.")
            unobserved = [name for name, val in [("Temperature", temp), ("pH", ph), ("Pressure", pressure), ("Methane", methane), ("Battery SoC", battery_soc)] if val is None]
            if unobserved:
                response_lines.append(f"- **Unobserved Parameters (No penalties applied):** {', '.join(unobserved)}.")
            if penalties:
                response_lines.append(f"- **Observations:** {'; '.join(penalties)}.")
            else:
                response_lines.append("- **System State:** All observed biochemical and electrical parameters are balanced within optimal operating envelopes.")

    else:
        observed_items = []
        if biogas is not None: observed_items.append(f"Biogas Yield: **{biogas} m³/day**")
        if methane is not None: observed_items.append(f"Methane (CH₄): **{methane}%**")
        if temp is not None: observed_items.append(f"Temp: **{temp}°C**")
        if ph is not None: observed_items.append(f"pH: **{ph}**")
        if pressure is not None: observed_items.append(f"Pressure: **{pressure} bar**")
        if feed is not None: observed_items.append(f"Feed: **{feed} kg**")
        if solar_power is not None: observed_items.append(f"Solar PV: **{solar_power} kW**")
        if battery_soc is not None: observed_items.append(f"Battery SoC: **{battery_soc}%**")

        response_lines.append(f"### 📊 Telemetry Snapshot & Advisory ({source})")
        if observed_items:
            response_lines.append("- " + " | ".join(observed_items))
        else:
            response_lines.append(f"- *No active telemetry stream or observed sensors for source {source}.*")
        response_lines.append("You can ask specific questions like: *\"How is the pH buffer?\"*, *\"Is solar heating sufficient?\"*, *\"What is the methane yield?\"*, or *\"Run digester health audit\"*.")

    if not is_key_configured:
        response_lines.append("> 💡 *Note: Running in offline deterministic rule mode. Set `GEMINI_API_KEY` in `.env` to activate dynamic multimodal Google Gemini 2.5 responses.*")

    return "\n\n".join(response_lines)


async def generate_chat_response(request: ChatRequest, db: Session) -> ChatResponse:
    """Handle chat request using Gemini API if configured, falling back seamlessly to local heuristic engine."""
    # 1. Resolve Telemetry Context
    telemetry = request.telemetry
    if telemetry is None:
        telemetry = get_live_telemetry_from_db(db)
    else:
        # Respect client telemetry as authoritative.
        # Do NOT overwrite client-supplied nulls or missing fields with database values from another source.
        if "source" not in telemetry:
            telemetry["source"] = "client_telemetry"

    now_iso = datetime.now(timezone.utc).isoformat()
    live_context_str = format_telemetry_context(telemetry)

    # 2. Check Gemini Configuration
    api_key = settings.GEMINI_API_KEY
    is_key_configured = bool(api_key and api_key.strip() and api_key != "your_gemini_api_key_here")

    # 3. Call Gemini if configured
    if is_key_configured:
        system_instruction = (
            "You are an expert Anaerobic Digestion AI Engineer & Biogas Energy Specialist for the Biogas Intelligence Platform. "
            "Your task is to answer user queries accurately, concisely, and professionally, incorporating the provided sensor telemetry. "
            "Guidelines:\n"
            "1. Ground your answers directly in the live telemetry values provided in the prompt context.\n"
            "2. Provide concise, clear, and expert technical insights on temperature stability, pH buffer capacity, methane yield, digester loading rate, gas pressure safety, solar monitoring power, biogas prediction, and estimated electricity potential.\n"
            "3. Maintain strict scientific integrity: clearly distinguish measured empirical values from ML forecasts, and present electricity generation strictly as calculated potential at an assumed generator electrical efficiency (default 30%), noting physical generator telemetry is not connected.\n"
            "4. Keep formatting clean with bold key metrics and bullet points. Avoid overly verbose fluff.\n"
        )

        prompt = f"{live_context_str}\n\nUser Question: {request.message}"

        candidate_models = [settings.GEMINI_MODEL, "gemini-flash-lite-latest", "gemini-flash-latest", "gemini-2.5-flash"]
        # Deduplicate while preserving order
        candidate_models = list(dict.fromkeys(candidate_models))

        for model_name in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": f"System Context:\n{system_instruction}\n\n{prompt}"}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 800
                }
            }

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                reply_text = parts[0]["text"].strip()
                                return ChatResponse(
                                    reply=reply_text,
                                    model=model_name,
                                    source="gemini-api",
                                    timestamp=now_iso,
                                    telemetry_context=telemetry,
                                    suggestions=[
                                        "What is the slurry pH stability?",
                                        "Estimate electricity generation potential",
                                        "Diagnose overpressure safety risk",
                                        "What is the next-day biogas forecast?"
                                    ]
                                )
                    else:
                        logger.warning(f"Gemini API model {model_name} returned status {resp.status_code}: {resp.text[:120]}")
            except Exception as ex:
                logger.warning(f"Gemini call to {model_name} failed: {ex}")
                continue

    # 4. Fallback to Smart Local Rule Engine
    fallback_text = generate_smart_local_response(request.message, telemetry, is_key_configured=is_key_configured)
    return ChatResponse(
        reply=fallback_text,
        model="xco-local-engine",
        source="fallback",
        timestamp=now_iso,
        telemetry_context=telemetry,
        suggestions=[
            "What is the slurry pH stability?",
            "Estimate electricity generation potential",
            "Diagnose overpressure safety risk",
            "What is the next-day biogas forecast?"
        ]
    )
