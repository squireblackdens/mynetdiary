import os
import time
import schedule
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

EMAIL = os.getenv("MND_EMAIL")
PASSWORD = os.getenv("MND_PASSWORD")

print("🚀 MyNetDiary Scheduler started", flush=True)
print(f"🌍 Timezone: {os.getenv('TZ')}", flush=True)

def run_job():
    print(f"🕑 Job started at {datetime.now()}", flush=True)

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": "/app/downloads",
        "download.prompt_for_download": False,
        "directory_upgrade": True
    })

    driver = webdriver.Chrome(options=chrome_options)
    try:
        driver.get("https://www.mynetdiary.com/login.do")
        driver.find_element(By.ID, "username").send_keys(EMAIL)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)
        driver.find_element(By.NAME, "login").click()
        time.sleep(3)

        driver.get("https://www.mynetdiary.com/reports.do")
        time.sleep(2)

        driver.find_element(By.LINK_TEXT, "Export").click()
        time.sleep(10)
    finally:
        driver.quit()

    print("✅ CSV downloaded.", flush=True)

# Run once immediately at startup
print("⚡ Running job immediately after container starts", flush=True)
run_job()

# Schedule daily run at 2am
schedule.every().day.at("02:00").do(run_job)
print("📆 Scheduled job to run at 02:00 daily", flush=True)

while True:
    schedule.run_pending()
    time.sleep(30)