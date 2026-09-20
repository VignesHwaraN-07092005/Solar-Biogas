import os
import sys
import json
import time

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000/dashboard"

diagnosis_report = {
    "condition_A_normal": {},
    "condition_B_cdn_blocked": {},
    "condition_C_chartjs_missing": {},
    "condition_D_xlsx_missing": {},
    "condition_E_delayed_script": {},
    "condition_F_fetch_resilience": {}
}

def run_diagnostics():
    print("==================================================")
    print("TASK 1 — REPRODUCE & DIAGNOSE CDN/CONNECTION ISSUES")
    print("==================================================")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)

        # ----------------------------------------------------
        # TEST A: NORMAL ACCESS
        # ----------------------------------------------------
        print("\n--- [CONDITION A] Normal Network Access ---")
        context_a = browser.new_context()
        page_a = context_a.new_page()
        console_a = []
        page_a.on("console", lambda m: console_a.append(f"[{m.type}] {m.text}"))
        page_a.on("pageerror", lambda e: console_a.append(f"[ERROR] {e}"))

        t0 = time.time()
        page_a.goto(BASE_URL, wait_until="load")
        load_time_a = time.time() - t0

        ready_state_a = page_a.evaluate("document.readyState")
        chart_defined_a = page_a.evaluate("typeof Chart !== 'undefined'")
        xlsx_defined_a = page_a.evaluate("typeof XLSX !== 'undefined'")
        biogas_kpi_a = page_a.locator("#kpi-current-biogas").text_content().strip()

        print(f"  Load Time: {load_time_a:.2f}s | readyState: {ready_state_a}")
        print(f"  Chart.js present: {chart_defined_a} | XLSX present: {xlsx_defined_a}")
        print(f"  Biogas KPI: '{biogas_kpi_a}'")
        print(f"  Console messages: {len(console_a)}")

        diagnosis_report["condition_A_normal"] = {
            "load_time_sec": round(load_time_a, 2),
            "ready_state": ready_state_a,
            "chart_defined": chart_defined_a,
            "xlsx_defined": xls_defined_a if 'xls_defined_a' in locals() else xlsx_defined_a,
            "biogas_kpi": biogas_kpi_a,
            "errors": [m for m in console_a if "error" in m.lower()]
        }
        context_a.close()

        # ----------------------------------------------------
        # TEST B: EXTERNAL CDN DNS FAILURE / BLOCKED CDN
        # ----------------------------------------------------
        print("\n--- [CONDITION B] External CDN Blocked (Simulating ERR_NAME_NOT_RESOLVED) ---")
        context_b = browser.new_context()
        page_b = context_b.new_page()
        console_b = []
        page_b.on("console", lambda m: console_b.append(f"[{m.type}] {m.text}"))
        page_b.on("pageerror", lambda e: console_b.append(f"[PAGEERROR] {e}"))

        # Abort all requests to external CDNs
        page_b.route("**/*jsdelivr.net/**", lambda route: route.abort("nameNotResolved"))
        page_b.route("**/*fonts.googleapis.com/**", lambda route: route.abort("nameNotResolved"))
        page_b.route("**/*fonts.gstatic.com/**", lambda route: route.abort("nameNotResolved"))

        t0 = time.time()
        page_b.goto(BASE_URL, wait_until="load")
        load_time_b = time.time() - t0

        ready_state_b = page_b.evaluate("document.readyState")
        chart_defined_b = page_b.evaluate("typeof Chart !== 'undefined'")
        xlsx_defined_b = page_b.evaluate("typeof XLSX !== 'undefined'")
        biogas_kpi_b = page_b.locator("#kpi-current-biogas").text_content().strip()

        print(f"  Load Time: {load_time_b:.2f}s | readyState: {ready_state_b}")
        print(f"  Chart.js present: {chart_defined_b} | XLSX present: {xlsx_defined_b}")
        print(f"  Biogas KPI: '{biogas_kpi_b}'")
        print(f"  Console errors: {[m for m in console_b if 'error' in m.lower()]}")

        diagnosis_report["condition_B_cdn_blocked"] = {
            "load_time_sec": round(load_time_b, 2),
            "ready_state": ready_state_b,
            "chart_defined": chart_defined_b,
            "xlsx_defined": xlsx_defined_b,
            "biogas_kpi": biogas_kpi_b,
            "errors": [m for m in console_b if "error" in m.lower()]
        }
        context_b.close()

        # ----------------------------------------------------
        # TEST C: CHART.JS MISSING / UNAVAILABLE
        # ----------------------------------------------------
        print("\n--- [CONDITION C] Chart.js Blocked/Unavailable ---")
        context_c = browser.new_context()
        page_c = context_c.new_page()
        console_c = []
        page_c.on("console", lambda m: console_c.append(f"[{m.type}] {m.text}"))
        page_c.on("pageerror", lambda e: console_c.append(f"[PAGEERROR] {e}"))

        # Block chart.min.js
        page_c.route("**/chart*.js", lambda route: route.abort("failed"))

        page_c.goto(BASE_URL, wait_until="load")
        page_c.wait_for_timeout(2000)

        chart_defined_c = page_c.evaluate("typeof Chart !== 'undefined'")
        ready_state_c = page_c.evaluate("document.readyState")
        biogas_kpi_c = page_c.locator("#kpi-current-biogas").text_content().strip()
        temp_kpi_c = page_c.locator("#kpi-temp-val").text_content().strip()
        status_kpi_c = page_c.locator("#kpi-status-text").text_content().strip()

        errors_c = [m for m in console_c if "error" in m.lower() or "referenceerror" in m.lower()]
        print(f"  Chart defined: {chart_defined_c}")
        print(f"  Biogas KPI: '{biogas_kpi_c}' | Temp KPI: '{temp_kpi_c}' | Status: '{status_kpi_c}'")
        print(f"  Errors captured: {errors_c}")

        diagnosis_report["condition_C_chartjs_missing"] = {
            "chart_defined": chart_defined_c,
            "biogas_kpi": biogas_kpi_c,
            "temp_kpi": temp_kpi_c,
            "errors": errors_c
        }
        context_c.close()

        # ----------------------------------------------------
        # TEST D: XLSX MISSING / UNAVAILABLE
        # ----------------------------------------------------
        print("\n--- [CONDITION D] XLSX Blocked/Unavailable ---")
        context_d = browser.new_context()
        page_d = context_d.new_page()
        console_d = []
        dialog_messages_d = []
        page_d.on("console", lambda m: console_d.append(f"[{m.type}] {m.text}"))
        page_d.on("pageerror", lambda e: console_d.append(f"[PAGEERROR] {e}"))
        page_d.on("dialog", lambda d: (dialog_messages_d.append(d.message), d.dismiss()))

        # Block xlsx
        page_d.route("**/xlsx*.js", lambda route: route.abort("failed"))

        page_d.goto(BASE_URL, wait_until="load")
        page_d.wait_for_timeout(2000)

        xlsx_defined_d = page_d.evaluate("typeof XLSX !== 'undefined'")
        print(f"  XLSX defined: {xlsx_defined_d}")

        # Attempt upload
        abs_excel = os.path.abspath("scratch/audit_test_files/test_A_exact_schema.xlsx")
        page_d.set_input_files("#scada-file-input", abs_excel)
        page_d.wait_for_timeout(2000)

        print(f"  Dialogs shown: {dialog_messages_d}")
        errors_d = [m for m in console_d if "error" in m.lower()]
        print(f"  Errors captured: {errors_d}")

        diagnosis_report["condition_D_xlsx_missing"] = {
            "xlsx_defined": xlsx_defined_d,
            "dialogs": dialog_messages_d,
            "errors": errors_d
        }
        context_d.close()

        # ----------------------------------------------------
        # TEST E: DELAYED SCRIPT LOADING
        # ----------------------------------------------------
        print("\n--- [CONDITION E] Delayed Script Loading (3000ms delay) ---")
        context_e = browser.new_context()
        page_e = context_e.new_page()

        def delay_script(route):
            time.sleep(3)
            route.continue_()

        page_e.route("**/chart*.js", delay_script)

        t0 = time.time()
        page_e.goto(BASE_URL, wait_until="domcontentloaded")
        dcl_time_e = time.time() - t0
        page_e.wait_for_load_state("load")
        load_time_e = time.time() - t0

        print(f"  DOMContentLoaded Time: {dcl_time_e:.2f}s | Load Time: {load_time_e:.2f}s")
        diagnosis_report["condition_E_delayed_script"] = {
            "dcl_time_sec": round(dcl_time_e, 2),
            "load_time_sec": round(load_time_e, 2)
        }
        context_e.close()

        browser.close()

    print("\n==================================================")
    print("DIAGNOSTIC RESULTS SUMMARY")
    print("==================================================")
    print(json.dumps(diagnosis_report, indent=2))

if __name__ == "__main__":
    run_diagnostics()
