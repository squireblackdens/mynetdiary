import os
import time
import schedule
import traceback
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from influxdb_client import InfluxDBClient, Point, WritePrecision
import pandas as pd  # Add pandas for Excel file processing

# InfluxDB v2 config (set these as environment variables)
INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")

# MyNetDiary credentials (set these as environment variables)
EMAIL = os.getenv("MYNETDIARY_EMAIL")
PASSWORD = os.getenv("MYNETDIARY_PASSWORD")

def run_job():
    print(f"🔄 Starting job at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    
    # Create a temporary directory for downloads
    import tempfile
    temp_dir = tempfile.mkdtemp()
    print(f"📁 Created temporary directory: {temp_dir}", flush=True)
    
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode (no GUI)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Configure download settings
    prefs = {
        "download.default_directory": temp_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "profile.default_content_setting_values.cookies": 1,  # Allow cookies (value 1 allows, 2 blocks)
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Set window size to ensure mobile elements don't appear
    chrome_options.add_argument("--window-size=1920,1080")

    driver = None
    
    try:
        print("🌐 Initializing Chrome WebDriver", flush=True)
        driver = webdriver.Chrome(options=chrome_options)
        
        # --- LOGIN ---
        print("🌐 Navigating to login page", flush=True)
        driver.get("https://www.mynetdiary.com/logonPage.do")
        
        # Add a screenshot of the login page for debugging
        login_screenshot = f"/app/downloads/login_page_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        driver.save_screenshot(login_screenshot)
        print(f"🖼 Login page screenshot: {login_screenshot}", flush=True)
        
        try:
            # Wait for the login form to be present
            print("⏳ Waiting for login form to load...", flush=True)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "username-or-email"))
            )
            
            # Fill in login details
            print("🔑 Filling login form", flush=True)
            username_field = driver.find_element(By.ID, "username-or-email")
            password_field = driver.find_element(By.ID, "password")
            username_field.send_keys(EMAIL)
            password_field.send_keys(PASSWORD)
            
            # Take screenshot before submitting
            pre_submit_screenshot = f"/app/downloads/pre_submit_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
            driver.save_screenshot(pre_submit_screenshot)
            print(f"🖼 Pre-submit screenshot: {pre_submit_screenshot}", flush=True)
            
            # Click sign in button using JavaScript as it's more reliable
            try:
                # Try to find the button and click it
                driver.execute_script("""
                var buttons = document.querySelectorAll('button');
                for(var i = 0; i < buttons.length; i++) {
                    var spans = buttons[i].querySelectorAll('span');
                    for(var j = 0; j < spans.length; j++) {
                        if(spans[j].textContent.trim() === 'SIGN IN') {
                            buttons[i].click();
                            return true;
                        }
                    }
                }
                return false;
                """)
                time.sleep(5)  # Give more time for the form to submit and process
            except Exception as e:
                print(f"⚠️ JavaScript form submission failed: {str(e)}", flush=True)
                
            print("🔐 Submitted login form", flush=True)

            # Take screenshot after submit
            post_submit_screenshot = f"/app/downloads/post_submit_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
            driver.save_screenshot(post_submit_screenshot)
            print(f"🖼 Post-submit screenshot: {post_submit_screenshot}", flush=True)

            # Print current URL for debugging
            print(f"🌐 Current URL after login submit: {driver.current_url}", flush=True)

            # Direct navigation to the URL that downloads the Excel file
            print("🔍 Navigating to XLS download URL", flush=True)
            driver.get("https://www.mynetdiary.com/exportData.do?year=2025")
            time.sleep(5)  # Wait for download to start
            
            # Take a screenshot after direct navigation to download URL
            direct_nav_screenshot = f"/app/downloads/direct_nav_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
            driver.save_screenshot(direct_nav_screenshot)
            print(f"🖼 Screenshot after navigation to download URL: {direct_nav_screenshot}", flush=True)
            
            # Check if we were redirected to login page
            if "logonPage.do" in driver.current_url or "signin" in driver.current_url.lower():
                print("⚠️ Redirected to login page, need to log in again", flush=True)
                # We're at the login page again, retry login
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username-or-email")))
                username_field = driver.find_element(By.ID, "username-or-email")
                password_field = driver.find_element(By.ID, "password")
                username_field.clear()
                password_field.clear()
                username_field.send_keys(EMAIL)
                password_field.send_keys(PASSWORD)
                
                # Use the explicit button click for the retry
                signin_button = driver.find_element(By.XPATH, "//button[.//span[text()='SIGN IN']]")
                driver.execute_script("arguments[0].click();", signin_button)
                print("🔐 Retried login submission", flush=True)
                time.sleep(5)
                
                retry_screenshot = f"/app/downloads/retry_login_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
                driver.save_screenshot(retry_screenshot)
                print(f"🖼 Screenshot after retry: {retry_screenshot}", flush=True)
                
                # Try direct navigation to download URL again
                driver.get("https://www.mynetdiary.com/exportData.do?year=2025")
                time.sleep(5)  # Wait for download to start

            # Wait for the download to complete
            print("⏳ Waiting for Excel file to download...", flush=True)
            
            # Wait up to 30 seconds for a file to appear in the download directory
            max_wait = 30
            wait_time = 0
            xls_file_path = None
            
            while wait_time < max_wait:
                # Check if any xls files have been downloaded
                xls_files = list(Path(temp_dir).glob("*.xls"))
                if xls_files:
                    xls_file_path = str(xls_files[0])
                    print(f"📄 Found downloaded file: {xls_file_path}", flush=True)
                    break
                time.sleep(1)
                wait_time += 1
            
            if not xls_file_path:
                print("⚠️ No Excel file was downloaded. Taking screenshot for debugging.", flush=True)
                export_error_screenshot = f"/app/downloads/export_error_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
                driver.save_screenshot(export_error_screenshot)
                print(f"🖼 Export error screenshot: {export_error_screenshot}", flush=True)
                raise Exception("Failed to download Excel file")
            
            # Process the Excel file
            print("📊 Processing Excel file...", flush=True)
            
            # Load the Excel file using pandas
            try:
                df = pd.read_excel(xls_file_path)
                print(f"📈 Successfully loaded Excel file with {len(df)} rows", flush=True)
                
                # Calculate the date for a week ago
                one_week_ago = datetime.now().date() - timedelta(days=7)
                
                # Filter data to only include the last week
                # Assuming there's a date column that can be parsed
                data_points = []
                
                # Loop through the Excel data
                for index, row in df.iterrows():
                    try:
                        # Try to parse the date from the row
                        row_date_str = row.get('Date', None)
                        if row_date_str:
                            # Try different date formats
                            try:
                                row_date = datetime.strptime(str(row_date_str), '%Y-%m-%d').date()
                            except ValueError:
                                try:
                                    row_date = datetime.strptime(str(row_date_str), '%m/%d/%Y').date()
                                except ValueError:
                                    print(f"⚠️ Could not parse date: {row_date_str}", flush=True)
                                    continue
                            
                            # Check if the row is from the last week
                            if row_date >= one_week_ago:
                                print(f"✅ Processing row for date: {row_date}", flush=True)
                                
                                # Create a data point for InfluxDB
                                point = Point("nutrition_data")
                                
                                # Add all fields from the row
                                for column, value in row.items():
                                    if pd.notnull(value):  # Only include non-null values
                                        if isinstance(value, (int, float)):
                                            point.field(column, value)
                                        else:
                                            # Try to convert to number if possible
                                            try:
                                                numeric_value = float(value)
                                                point.field(column, numeric_value)
                                            except (ValueError, TypeError):
                                                # Keep as tag if conversion fails
                                                point.tag(column, str(value))
                                
                                # Use the row date for the timestamp
                                timestamp = datetime.combine(row_date, datetime.min.time())
                                point.time(timestamp, WritePrecision.NS)
                                
                                data_points.append(point)
                            else:
                                print(f"⏭️ Skipping row for date: {row_date} (before {one_week_ago})", flush=True)
                    except Exception as row_err:
                        print(f"⚠️ Error processing row: {row_err}", flush=True)
                        continue
                
                # Write the data points to InfluxDB
                if data_points:
                    print(f"📤 Writing {len(data_points)} data points to InfluxDB", flush=True)
                    
                    with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG) as client:
                        write_api = client.write_api()
                        write_api.write(bucket=INFLUX_BUCKET, record=data_points)
                        print("✅ Successfully wrote data to InfluxDB", flush=True)
                else:
                    print("⚠️ No data points to write to InfluxDB", flush=True)
                
                # Clean up the Excel file now that we're done with it
                try:
                    os.remove(xls_file_path)
                    print(f"🗑️ Deleted Excel file: {xls_file_path}", flush=True)
                except Exception as del_err:
                    print(f"⚠️ Could not delete Excel file: {del_err}", flush=True)
                
            except Exception as excel_err:
                print(f"❌ Error processing Excel file: {excel_err}", flush=True)
                traceback.print_exc()
                
                # Try to clean up the Excel file even if processing failed
                try:
                    if xls_file_path and os.path.exists(xls_file_path):
                        os.remove(xls_file_path)
                        print(f"🗑️ Deleted Excel file after error: {xls_file_path}", flush=True)
                except Exception as del_err:
                    print(f"⚠️ Could not delete Excel file after error: {del_err}", flush=True)
        
        except Exception as form_err:
            print(f"❌ Error with login form: {form_err}", flush=True)

    except Exception as e:
        error_time = datetime.now().strftime("%Y%m%d-%H%M%S")
        screenshot = f"/app/downloads/error_{error_time}.png"
        html_dump = f"/app/downloads/error_{error_time}.html"

        try:
            if driver is not None:
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
        # Clean up resources
        if driver is not None:
            driver.quit()
        
        # Try to clean up the temp directory
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"🧹 Cleaned up temporary directory: {temp_dir}", flush=True)
        except Exception as cleanup_err:
            print(f"⚠️ Could not clean up temporary directory: {cleanup_err}", flush=True)

# Run immediately on startup for testing
print("🚀 Starting MyNetDiary data collector", flush=True)
run_job()

# Schedule to run weekly on Sunday at 2am
schedule.every().sunday.at("02:00").do(run_job)
print("⏰ Scheduled to run weekly on Sunday at 02:00", flush=True)

# Add a short delay before entering the main loop
time.sleep(5)

while True:
    schedule.run_pending()
    time.sleep(30)