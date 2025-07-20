import os
import time
import schedule
import traceback
from pathlib import Path
from datetime import datetime, date, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from influxdb_client import InfluxDBClient, Point, WritePrecision

# InfluxDB v2 config (set these as environment variables)
INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")

EMAIL = os.getenv("MND_EMAIL")
PASSWORD = os.getenv("MND_PASSWORD")



def run_job():
    print(f"🕑 Job started at {datetime.now()}", flush=True)

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.cookies": 2,
        "download.prompt_for_download": False,
        "directory_upgrade": True
    })

    driver = webdriver.Chrome(options=chrome_options)

    try:
        # --- LOGIN ---
        print("🌐 Navigating to login page", flush=True)
        driver.get("https://www.mynetdiary.com/logonPage.do")

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username-or-email")))
        driver.find_element(By.ID, "username-or-email").send_keys(EMAIL)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)
        driver.find_element(By.XPATH, "//button[.//span[text()='SIGN IN']]").click()
        print("🔐 Submitted login form", flush=True)

        # Wait for either dashboard or login error or URL change
        time.sleep(2)  # Give JS a moment to process

        # Print current URL for debugging
        print(f"🌐 Current URL after login submit: {driver.current_url}", flush=True)

        # Wait up to 15s for either dashboard, or error message, or URL change
        dashboard_xpath = "//div[contains(@class, 'MuiTabs-flexContainer') and @role='tablist']//button[.//span[text()='Dashboard']]"
        login_error_xpath = "//div[contains(@class, 'signin__notification')]"
        initial_url = driver.current_url

        try:
            WebDriverWait(driver, 15).until(
                lambda d: (
                    d.current_url != initial_url or
                    d.find_elements(By.XPATH, dashboard_xpath) or
                    d.find_elements(By.XPATH, login_error_xpath)
                )
            )
        except Exception:
            print("❌ Neither dashboard nor error message appeared, and URL did not change.", flush=True)

        # Check for login error
        error_elems = driver.find_elements(By.XPATH, login_error_xpath)
        if error_elems:
            print("❌ Login error detected.", flush=True)
            print(f"🔎 Error message: {error_elems[0].text}", flush=True)
            # Save HTML and screenshot for debugging
            fail_time = datetime.now().strftime("%Y%m%d-%H%M%S")
            fail_html = f"/app/downloads/login_error_{fail_time}.html"
            fail_screenshot = f"/app/downloads/login_error_{fail_time}.png"
            with open(fail_html, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            driver.save_screenshot(fail_screenshot)
            print(f"📝 HTML with login error saved: {fail_html}", flush=True)
            print(f"🖼 Screenshot with login error saved: {fail_screenshot}", flush=True)
            raise Exception("Login failed, see error message above.")

        # Check for dashboard
        dashboard_elems = driver.find_elements(By.XPATH, dashboard_xpath)
        if dashboard_elems:
            print("✅ Login successful - Dashboard tab detected", flush=True)
            print("✅ Login successful", flush=True)
        else:
            print("❌ Dashboard tab not found after login, but no explicit error message.", flush=True)
            # Save HTML and screenshot for debugging
            fail_time = datetime.now().strftime("%Y%m%d-%H%M%S")
            fail_html = f"/app/downloads/dashboard_not_found_{fail_time}.html"
            fail_screenshot = f"/app/downloads/dashboard_not_found_{fail_time}.png"
            with open(fail_html, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            driver.save_screenshot(fail_screenshot)
            print(f"📝 HTML with missing dashboard saved: {fail_html}", flush=True)
            print(f"🖼 Screenshot with missing dashboard saved: {fail_screenshot}", flush=True)
            raise Exception("Login did not reach dashboard.")

        # --- REPORT PAGE ---
        print("📊 Opening reports page", flush=True)
        driver.get("https://www.mynetdiary.com/reports.do")

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "lstPeriodOptions")))
        Select(driver.find_element(By.ID, "lstPeriodOptions")).select_by_value("periodCustom")

        yesterday = (date.today() - timedelta(days=1)).strftime("%d/%m/%Y")
        today = date.today().strftime("%d/%m/%Y")
        driver.execute_script(f"document.getElementById('startDate').value = '{yesterday}'")
        driver.execute_script(f"document.getElementById('endDate').value = '{today}'")
        print(f"📅 Set date range: {yesterday} to {today}", flush=True)

        # Wait for the report table
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.report"))
        )
        print("✅ Report table loaded", flush=True)

        # You can now continue parsing or injecting to Influx as before

    except Exception as e:
        error_time = datetime.now().strftime("%Y%m%d-%H%M%S")
        screenshot = f"/app/downloads/error_{error_time}.png"
        html_dump = f"/app/downloads/error_{error_time}.html"

        try:
            driver.save_screenshot(screenshot)
            with open(html_dump, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"🖼 Screenshot saved: {screenshot}", flush=True)
            print(f"📝 HTML saved: {html_dump}", flush=True)
        except Exception as dump_err:
            print(f"⚠️ Could not save debug info: {dump_err}", flush=True)

        print("❌ ERROR: Exception occurred during job run", flush=True)
        traceback.print_exc()

    finally:
        driver.quit()

# Run immediately
run_job()

# Schedule 2am daily
schedule.every().day.at("02:00").do(run_job)
print("📆 Scheduled daily run at 02:00", flush=True)

while True:
    schedule.run_pending()
    time.sleep(30)