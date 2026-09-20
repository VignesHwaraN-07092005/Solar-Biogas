import os
import sys
import time
import subprocess
from playwright.sync_api import sync_playwright

# Start a temporary uvicorn instance on port 8009 to capture the compiled styles
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8009"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)
time.sleep(3)


try:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8009/dashboard", wait_until="load")
        page.wait_for_timeout(3000)


        # Extract all style tags
        styles = page.evaluate("""() => {
            const allStyles = Array.from(document.querySelectorAll('style'));
            return allStyles.map(s => s.textContent).join('\\n\\n');
        }""")

        out_path = os.path.join("frontend", "public", "tailwind.min.css")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(styles)

        print(f"Extracted {len(styles)} bytes of compiled Tailwind CSS into {out_path}")
        browser.close()
finally:
    proc.terminate()
    proc.wait()
