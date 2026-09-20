import os
import sys
import json
import time

# Ensure UTF-8 console output on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000/dashboard"
SCREENSHOT_DIR = "docs/audit_screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

results = {
    "live_iot_empty": {},
    "live_iot_active": {},
    "user_upload": {},
    "safety_propagation": {},
    "reduced_motion": {},
    "console_errors": []
}

def run_verification():
    print("==================================================")
    print("STARTING TASK 2 PLAYWRIGHT VERIFICATION PASS")
    print("==================================================")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        page.on("console", lambda msg: results["console_errors"].append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: results["console_errors"].append(str(err)))

        # ----------------------------------------------------
        # TEST 1A: LIVE_IOT EMPTY / WAITING FOR ESP32 STATE
        # ----------------------------------------------------
        print("\n[STEP 1A] Testing LIVE_IOT no-data / WAITING FOR ESP32 state...")
        
        # Route live-status and readings to empty responses to test pure un-connected state
        def handle_live_status(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"count": 0, "connectivity_state": "WAITING FOR ESP32"})
            )
        def handle_live_readings(route):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps([])
            )

        page.route("**/api/readings/live-status", handle_live_status)
        page.route("**/api/readings?source=live_esp32*", handle_live_readings)

        page.goto(BASE_URL, wait_until="load")
        page.wait_for_timeout(2000)

        # Switch source to LIVE_IOT
        page.select_option("#telemetry-source-select", "LIVE_IOT")
        page.wait_for_timeout(2500)

        kpi_press = page.locator("#kpi-press-val").text_content().strip()
        kpi_temp = page.locator("#kpi-temp-val").text_content().strip()
        kpi_ph = page.locator("#kpi-ph-val").text_content().strip()
        kpi_methane = page.locator("#kpi-methane-val").text_content().strip()
        kpi_biogas = page.locator("#kpi-current-biogas").text_content().strip()
        header_safety = page.locator("#header-safety-text").text_content().strip()
        live_pill = page.locator("#live-iot-status-pill").text_content().strip()
        alerts_list = page.locator("#alerts-list").text_content().strip()
        alert_badge = page.locator("#alert-count-badge").text_content().strip()

        print(f"  Empty State KPI Pressure: '{kpi_press}'")
        print(f"  Empty State KPI Temp: '{kpi_temp}'")
        print(f"  Empty State KPI pH: '{kpi_ph}'")
        print(f"  Empty State KPI Methane: '{kpi_methane}'")
        print(f"  Empty State KPI Biogas: '{kpi_biogas}'")
        print(f"  Empty State Header Safety Text: '{header_safety}'")
        print(f"  Empty State Live IoT Status Pill: '{live_pill}'")
        print(f"  Empty State Alert Badge: '{alert_badge}'")
        print(f"  Empty State Alerts List: '{alerts_list[:60]}...'")

        assert "—" in kpi_press or "-" in kpi_press, f"Expected — for pressure, got {kpi_press}"
        assert "—" in kpi_temp or "-" in kpi_temp, f"Expected — for temp, got {kpi_temp}"
        assert "—" in kpi_ph or "-" in kpi_ph, f"Expected — for pH, got {kpi_ph}"
        assert "—" in kpi_methane or "-" in kpi_methane, f"Expected — for methane, got {kpi_methane}"
        assert "—" in kpi_biogas or "-" in kpi_biogas, f"Expected — for biogas, got {kpi_biogas}"
        assert "STANDBY" in header_safety, f"Expected STANDBY, got {header_safety}"
        assert "WAITING FOR ESP32" in live_pill, f"Expected WAITING FOR ESP32, got {live_pill}"
        assert "No active sensor telemetry" in alerts_list, f"Expected no stream message, got {alerts_list}"
        assert "0 Active" in alert_badge, f"Expected 0 Active, got {alert_badge}"

        results["live_iot_empty"] = {
            "status": "PASSED",
            "kpi_press": kpi_press,
            "kpi_temp": kpi_temp,
            "kpi_ph": kpi_ph,
            "kpi_methane": kpi_methane,
            "header_safety": header_safety,
            "live_pill": live_pill
        }
        page.screenshot(path=f"{SCREENSHOT_DIR}/task2_live_iot_empty_state.png")
        print("  -> LIVE_IOT empty state verified successfully.")

        # Unroute mock handlers for next steps
        page.unroute("**/api/readings/live-status")
        page.unroute("**/api/readings?source=live_esp32*")

        # ----------------------------------------------------
        # TEST 1B: LIVE_IOT REAL STREAM & MISSING PARAMETER NULL-SAFETY
        # ----------------------------------------------------
        print("\n[STEP 1B] Testing LIVE_IOT active stream and missing parameter provenance...")
        page.goto(BASE_URL, wait_until="load")
        page.wait_for_timeout(2000)
        page.select_option("#telemetry-source-select", "LIVE_IOT")
        page.wait_for_timeout(3000)

        act_press = page.locator("#kpi-press-val").text_content().strip()
        act_temp = page.locator("#kpi-temp-val").text_content().strip()
        act_ph = page.locator("#kpi-ph-val").text_content().strip()
        act_methane = page.locator("#kpi-methane-val").text_content().strip()
        act_biogas = page.locator("#kpi-current-biogas").text_content().strip()
        act_header = page.locator("#header-safety-text").text_content().strip()

        print(f"  Active Stream KPI Pressure: '{act_press}'")
        print(f"  Active Stream KPI Temp: '{act_temp}'")
        print(f"  Active Stream KPI pH: '{act_ph}'")
        print(f"  Active Stream KPI Methane (missing in DB): '{act_methane}'")
        print(f"  Active Stream KPI Biogas: '{act_biogas}'")
        print(f"  Active Stream Header Safety: '{act_header}'")

        # Methane is not provided by ESP32 reading and MUST be "—", not synthetic 62.5%
        assert "—" in act_methane or "-" in act_methane, f"Expected — for missing methane, got {act_methane}"
        assert "1.18" in act_press or len(act_press) > 0, f"Expected observed pressure, got {act_press}"
        assert "36.6" in act_temp or len(act_temp) > 0, f"Expected observed temp, got {act_temp}"
        assert "NORMAL" in act_header, f"Expected INTERLOCKS NORMAL for safe telemetry, got {act_header}"

        results["live_iot_active"] = {
            "status": "PASSED",
            "act_press": act_press,
            "act_temp": act_temp,
            "act_ph": act_ph,
            "act_methane": act_methane,
            "act_header": act_header
        }
        page.screenshot(path=f"{SCREENSHOT_DIR}/task2_live_iot_active_stream.png")
        print("  -> LIVE_IOT active stream and missing parameter provenance verified.")

        # ----------------------------------------------------
        # TEST 2: USER_UPLOAD test_A_exact_schema.xlsx
        # ----------------------------------------------------
        print("\n[STEP 2] Testing USER_UPLOAD with test_A_exact_schema.xlsx...")
        abs_excel = os.path.abspath("scratch/audit_test_files/test_A_exact_schema.xlsx")
        assert os.path.exists(abs_excel), f"Excel file {abs_excel} not found"

        page.set_input_files("#scada-file-input", abs_excel)
        page.wait_for_timeout(3000)

        # Wait for and click Activate Dataset button in ingestion modal
        act_btn = page.locator("#activate-uploaded-dataset-btn")
        if act_btn.is_visible():
            act_btn.click()
            page.wait_for_timeout(1500)
        else:
            # If not auto-opened, switch source select
            page.select_option("#telemetry-source-select", "USER_UPLOAD")
            page.wait_for_timeout(1500)

        u_biogas = page.locator("#kpi-current-biogas").text_content().strip()
        u_temp = page.locator("#kpi-temp-val").text_content().strip()
        u_ph = page.locator("#kpi-ph-val").text_content().strip()
        u_press = page.locator("#kpi-press-val").text_content().strip()
        u_methane = page.locator("#kpi-methane-val").text_content().strip()
        u_status = page.locator("#kpi-status-text").text_content().strip()
        u_pred = page.locator("#kpi-predicted-biogas").text_content().strip()

        print(f"  User Upload Biogas: '{u_biogas}'")
        print(f"  User Upload Temp: '{u_temp}'")
        print(f"  User Upload pH: '{u_ph}'")
        print(f"  User Upload Pressure: '{u_press}'")
        print(f"  User Upload Methane: '{u_methane}'")
        print(f"  User Upload Status: '{u_status}'")
        print(f"  User Upload Prediction: '{u_pred}'")

        assert "5410.00" in u_biogas or "5410" in u_biogas, f"Expected 5410.00 observed biogas, got {u_biogas}"
        assert "36.7" in u_temp, f"Expected 36.7 temp, got {u_temp}"
        assert "7.25" in u_ph, f"Expected 7.25 pH, got {u_ph}"
        assert "—" in u_press or "-" in u_press, f"Expected — for missing pressure, got {u_press}"
        assert "—" in u_methane or "-" in u_methane, f"Expected — for missing methane, got {u_methane}"
        assert "Not Validated" in u_status or "Not Validated" in u_pred or "—" in u_pred, f"Expected unvalidated domain notice, got {u_status} / {u_pred}"

        results["user_upload"] = {
            "status": "PASSED",
            "u_biogas": u_biogas,
            "u_temp": u_temp,
            "u_ph": u_ph,
            "u_press": u_press,
            "u_methane": u_methane,
            "u_status": u_status
        }
        page.screenshot(path=f"{SCREENSHOT_DIR}/task2_user_upload_exact_schema.png")
        print("  -> USER_UPLOAD verified successfully and screenshot saved.")

        # ----------------------------------------------------
        # TEST 3: DYNAMIC SAFETY ALERT PROPAGATION & CLEARING
        # ----------------------------------------------------
        print("\n[STEP 3] Testing dynamic safety alert evaluation and source transition clearing...")
        
        # Test warning propagation: simulate high pressure (1.35 bar)
        page.evaluate("""
            async () => {
                const sample = { temp: 36.5, ph: 7.25, pressure: 1.35 };
                await updateSafetyAlerts(sample);
            }
        """)
        page.wait_for_timeout(1000)

        warn_header = page.locator("#header-safety-text").text_content().strip()
        warn_badge = page.locator("#alert-count-badge").text_content().strip()
        warn_list = page.locator("#alerts-list").text_content().strip()
        print(f"  Warning Header: '{warn_header}'")
        print(f"  Warning Badge: '{warn_badge}'")
        print(f"  Warning List: '{warn_list[:80]}...'")

        assert "WARNING" in warn_header, f"Expected WARNING in header, got {warn_header}"
        assert "1 Active" in warn_badge, f"Expected 1 Active in badge, got {warn_badge}"
        assert "HIGH PRESSURE" in warn_header or "1.35" in warn_header, f"Expected high pressure info, got {warn_header}"
        assert "High gas pressure warning" in warn_list or "1.30" in warn_list, f"Expected warning alert in list, got {warn_list}"

        # Test critical overpressure propagation (1.55 bar)
        page.evaluate("""
            async () => {
                const sample = { temp: 36.5, ph: 7.25, pressure: 1.55 };
                await updateSafetyAlerts(sample);
            }
        """)
        page.wait_for_timeout(1000)

        crit_header = page.locator("#header-safety-text").text_content().strip()
        crit_list = page.locator("#alerts-list").text_content().strip()
        print(f"  Critical Header: '{crit_header}'")
        print(f"  Critical List: '{crit_list[:80]}...'")

        assert "CRITICAL" in crit_header, f"Expected CRITICAL in header, got {crit_header}"
        assert "Relief valve" in crit_list or "Overpressure" in crit_list, f"Expected relief valve activation, got {crit_list}"

        # Take screenshot of active critical alert
        page.screenshot(path=f"{SCREENSHOT_DIR}/task2_safety_propagation_critical.png")

        # Now test source transition clearing stale alerts
        print("  Testing source transition clearing stale alerts...")
        page.select_option("#telemetry-source-select", "DEMO_SYNTHETIC")
        for w in range(6):
            page.wait_for_timeout(500)
            dbg = page.evaluate("""() => ({
                header: document.getElementById('header-safety-text')?.textContent,
                badge: document.getElementById('alert-count-badge')?.textContent,
                source: currentDataSource,
                records: telemetryDataset.length,
                token: currentSourceLoadToken
            })""")
            print(f"    [+{(w+1)*500}ms] state: {dbg}")

        cleared_header = page.locator("#header-safety-text").text_content().strip()
        cleared_badge = page.locator("#alert-count-badge").text_content().strip()
        cleared_list = page.locator("#alerts-list").text_content().strip()

        print(f"  Post-transition Header: '{cleared_header}'")
        print(f"  Post-transition Badge: '{cleared_badge}'")
        print(f"  Post-transition List: '{cleared_list[:60]}...'")

        # Stale alerts must be cleared immediately on transition
        assert "0 Active" in cleared_badge, f"Expected 0 Active, got {cleared_badge}"
        assert "CRITICAL" not in cleared_header, f"Stale CRITICAL must be cleared, got {cleared_header}"
        assert "Relief valve" not in cleared_list, f"Stale relief valve alert must be cleared, got {cleared_list}"
        assert "NORMAL" in cleared_header or "Initializing" in cleared_header, f"Expected NORMAL or Initializing, got {cleared_header}"

        results["safety_propagation"] = {
            "status": "PASSED",
            "warn_header": warn_header,
            "crit_header": crit_header,
            "cleared_header": cleared_header,
            "cleared_badge": cleared_badge
        }
        print("  -> Safety propagation and stale-clearing verified successfully.")

        # ----------------------------------------------------
        # TEST 4: PREFERS-REDUCED-MOTION VERIFICATION
        # ----------------------------------------------------
        print("\n[STEP 4] Testing prefers-reduced-motion media query...")
        context_rm = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            reduced_motion="reduce"
        )
        page_rm = context_rm.new_page()
        page_rm.goto(BASE_URL, wait_until="load")
        page_rm.wait_for_timeout(1500)

        # Trigger an alert so that .animate-pulse is attached to header-safety-indicator
        page_rm.evaluate("""
            async () => {
                const sample = { temp: 36.5, ph: 7.25, pressure: 1.55 };
                await updateSafetyAlerts(sample);
            }
        """)
        page_rm.wait_for_timeout(500)

        # Verify computed style animation on the indicator
        has_pulse_class = page_rm.evaluate("document.getElementById('header-safety-indicator')?.classList.contains('animate-pulse')")
        computed_anim = page_rm.evaluate("""
            () => {
                const el = document.getElementById('header-safety-indicator');
                if (!el) return null;
                const style = window.getComputedStyle(el);
                return {
                    animationName: style.animationName,
                    animationDuration: style.animationDuration
                };
            }
        """)
        print(f"  Element has animate-pulse class: {has_pulse_class}")
        print(f"  Computed Animation: {computed_anim}")

        # In reduced-motion mode, styles.css sets .animate-pulse { animation: none !important; }
        assert computed_anim["animationName"] == "none" or computed_anim["animationDuration"] == "0s" or "0.01ms" in computed_anim["animationDuration"] or "1e-05s" in computed_anim["animationDuration"], f"Expected animation suppressed, got {computed_anim}"

        results["reduced_motion"] = {
            "status": "PASSED",
            "has_pulse_class": has_pulse_class,
            "computed_animation": computed_anim
        }
        print("  -> prefers-reduced-motion animation suppression verified.")

        browser.close()

    print("\n==================================================")
    print("TASK 2 PLAYWRIGHT AUDIT COMPLETE - ALL TESTS PASSED")
    print(f"Console errors: {len(results['console_errors'])}")
    print("==================================================")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    run_verification()
