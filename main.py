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

# def run_job():
#     print(f"🕑 Job started at {datetime.now()}", flush=True)

#     chrome_options = Options()
#     chrome_options.add_argument("--headless=new")
#     chrome_options.add_argument("--no-sandbox")
#     chrome_options.add_argument("--disable-dev-shm-usage")
#     chrome_options.add_argument("--disable-gpu")

#     chrome_options.add_experimental_option("prefs", {
#         "profile.default_content_setting_values.cookies": 2,
#         "download.prompt_for_download": False,
#         "directory_upgrade": True
#     })

#     driver = webdriver.Chrome(options=chrome_options)

#     try:
#         # Login
#         driver.get("https://www.mynetdiary.com/logonPage.do")
#         WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username-or-email")))
#         driver.find_element(By.ID, "username-or-email").send_keys(EMAIL)
#         driver.find_element(By.ID, "password").send_keys(PASSWORD)
#         driver.find_element(By.XPATH, "//button[.//span[text()='SIGN IN']]").click()

#         WebDriverWait(driver, 10).until(EC.url_contains("dashboard"))
#         driver.get("https://www.mynetdiary.com/reports.do")
#         WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "lstPeriodOptions")))
#         Select(driver.find_element(By.ID, "lstPeriodOptions")).select_by_value("periodCustom")

#         # Set custom dates (yesterday–today)
#         yesterday = (date.today() - timedelta(days=1)).strftime("%d/%m/%Y")
#         today = date.today().strftime("%d/%m/%Y")
#         driver.execute_script(f"document.getElementById('startDate').value = '{yesterday}'")
#         driver.execute_script(f"document.getElementById('endDate').value = '{today}'")
#         time.sleep(1)

#         # Wait for report table to load
#         WebDriverWait(driver, 10).until(
#             EC.presence_of_element_located((By.CSS_SELECTOR, "table.report"))
#         )
#         print("📊 Report table loaded", flush=True)

#         rows = driver.find_elements(By.CSS_SELECTOR, "table.report tbody tr")
#         current_category = None
#         data_points = []

#         for row in rows:
#             tds = row.find_elements(By.TAG_NAME, "td")
#             if not tds:
#                 continue

#             # Detect categories like Lunch / Left / Target
#             if "class" in row.get_attribute("outerHTML") and "nutrientTotals" in row.get_attribute("outerHTML"):
#                 current_category = tds[0].text.strip()
#                 values = [td.text.replace("cals", "").replace("mg", "").replace("g", "").replace(",", "").strip() for td in tds[3:]]
#                 fields = ["calories", "fat", "carbs", "protein", "sat_fat", "trans_fat", "net_carbs", "fiber", "sodium", "calcium"]

#                 # Clean and convert values
#                 fields_dict = {}
#                 for key, value in zip(fields, values):
#                     try:
#                         fields_dict[key] = float(value)
#                     except:
#                         continue  # skip missing or empty

#                 point = (
#                     Point("nutrition")
#                     .tag("source", "mynetdiary")
#                     .tag("type", current_category)
#                     .field("calories", fields_dict.get("calories", 0))
#                     .field("fat", fields_dict.get("fat", 0))
#                     .field("carbs", fields_dict.get("carbs", 0))
#                     .field("protein", fields_dict.get("protein", 0))
#                     .field("sodium", fields_dict.get("sodium", 0))
#                     .time(datetime.utcnow(), WritePrecision.NS)
#                 )
#                 data_points.append(point)

#         print(f"✅ Parsed {len(data_points)} points", flush=True)

#         # Send to InfluxDB v2
#         if INFLUX_URL and INFLUX_TOKEN:
#             with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
#                 write_api = client.write_api()
#                 write_api.write(bucket=INFLUX_BUCKET, record=data_points)
#                 print(f"📤 Uploaded {len(data_points)} points to InfluxDB", flush=True)
#         else:
#             print("⚠️ No InfluxDB config found", flush=True)

#     except Exception as e:
#         print(f"❌ ERROR: {e}", flush=True)
#     finally:
#         driver.quit()

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

        WebDriverWait(driver, 10).until(EC.url_contains("dashboard"))
        print("✅ Login successful", flush=True)

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