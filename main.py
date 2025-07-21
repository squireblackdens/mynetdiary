import os
import time
import schedule
import traceback
import re
import csv
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
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

# MyNetDiary credentials (set these as environment variables)
EMAIL = os.getenv("MND_EMAIL")
PASSWORD = os.getenv("MND_PASSWORD")

def run_job():
    print(f"🕑 Job started at {datetime.now()}", flush=True)

    # Create a unique temporary directory for Chrome user data
    import tempfile
    temp_dir = tempfile.mkdtemp(prefix="chrome_user_data_")
    print(f"📁 Created temporary directory: {temp_dir}", flush=True)
    
    chrome_options = Options()
    # Re-enable headless mode as this is likely running in a container
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Specify unique user data directory to avoid conflicts
    chrome_options.add_argument(f"--user-data-dir={temp_dir}")
    
    # Add user agent to appear as a regular browser
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")
    
    # Enable cookies for the login process and configure downloads
    prefs = {
        # Allow cookies (value 1 allows, 2 blocks)
        "profile.default_content_setting_values.cookies": 1,
        "download.default_directory": temp_dir,
        "download.prompt_for_download": False,
        "directory_upgrade": True
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

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username-or-email")))
        
        # Fill in the form fields
        username_field = driver.find_element(By.ID, "username-or-email")
        password_field = driver.find_element(By.ID, "password")
        
        # Clear fields first to ensure clean input
        username_field.clear()
        password_field.clear()
        
        # Type the credentials
        username_field.send_keys(EMAIL)
        print(f"✓ Entered email: {EMAIL[:3]}...{EMAIL[-3:]}", flush=True)
        password_field.send_keys(PASSWORD)
        print("✓ Entered password", flush=True)
        
        # Optional: Check the "Remember me" checkbox
        try:
            remember_me = driver.find_element(By.XPATH, "//input[@type='checkbox' and contains(@class, 'jss107')]")
            if not remember_me.is_selected():
                # Click the parent span since the checkbox might be hidden
                remember_me_label = driver.find_element(By.XPATH, "//span[contains(@class, 'MuiTypography-body1') and text()='Remember me on this computer']")
                remember_me_label.click()
                print("✓ Selected 'Remember me' checkbox", flush=True)
        except Exception as e:
            print(f"ℹ️ Could not select 'Remember me' checkbox: {str(e)}", flush=True)
        
        # Take screenshot before submitting
        pre_submit_screenshot = f"/app/downloads/pre_submit_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        driver.save_screenshot(pre_submit_screenshot)
        print(f"🖼 Pre-submit screenshot: {pre_submit_screenshot}", flush=True)
        
        # Click the sign-in button using JavaScript for more reliability
        try:
            print("🔐 Submitting form with JavaScript", flush=True)
            driver.execute_script("""
                var buttons = document.querySelectorAll('button');
                for(var i=0; i<buttons.length; i++) {
                    if(buttons[i].innerText.includes('SIGN IN')) {
                        buttons[i].click();
                        return true;
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

        # Navigate directly to XLS export URL
        print("🔍 Navigating to XLS download URL", flush=True)
        driver.get("https://www.mynetdiary.com/exportData.do?year=2025")
        time.sleep(5)  # Wait for download to start
        
        # Take a screenshot after navigation to download URL
        direct_nav_screenshot = f"/app/downloads/direct_nav_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        driver.save_screenshot(direct_nav_screenshot)
        print(f"🖼 Screenshot after navigation to download URL: {direct_nav_screenshot}", flush=True)
        
        # Check if we need to login again
        if "logonPage.do" in driver.current_url or "signin" in driver.current_url.lower():
            print("⚠️ Redirected to login page, need to log in again", flush=True)
            
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
            
            retry_download_screenshot = f"/app/downloads/retry_download_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
            driver.save_screenshot(retry_download_screenshot)
            print(f"🖼 Screenshot after retry to download URL: {retry_download_screenshot}", flush=True)

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
        
        # Process the Excel file using built-in modules instead of pandas
        print("📊 Processing Excel file...", flush=True)
        
        try:
            # Use csv module to read XLS (works for simple Excel files)
            # One week ago from today
            one_week_ago = datetime.now().date() - timedelta(days=7)
            data_points = []
            
            # Process the XLS file
            import xlrd  # Try to use xlrd if available
            
            try:
                # Try xlrd first
                workbook = xlrd.open_workbook(xls_file_path)
                sheet = workbook.sheet_by_index(0)
                
                # Get headers from first row
                headers = [sheet.cell_value(0, col) for col in range(sheet.ncols)]
                print(f"📊 Found headers: {headers}", flush=True)
                
                # Process rows
                for row_idx in range(1, sheet.nrows):
                    try:
                        row_data = {}
                        for col_idx in range(sheet.ncols):
                            cell_value = sheet.cell_value(row_idx, col_idx)
                            if col_idx < len(headers):
                                row_data[headers[col_idx]] = cell_value
                        
                        # Process row data and check date
                        row_date_str = row_data.get('Date', None)
                        if row_date_str:
                            # Try to parse the date
                            try:
                                if isinstance(row_date_str, str):
                                    # Try different date formats
                                    date_formats = ['%Y-%m-%d', '%m/%d/%Y']
                                    for fmt in date_formats:
                                        try:
                                            row_date = datetime.strptime(row_date_str, fmt).date()
                                            break
                                        except ValueError:
                                            continue
                                    else:
                                        print(f"⚠️ Could not parse date string: {row_date_str}", flush=True)
                                        continue
                                elif isinstance(row_date_str, float):
                                    # Handle Excel date (float days since 1900-01-01)
                                    # Excel dates are days since 1899-12-30 (1 = 1900-01-01)
                                    delta_days = int(row_date_str)
                                    base_date = datetime(1899, 12, 30).date()
                                    row_date = base_date + timedelta(days=delta_days)
                                else:
                                    print(f"⚠️ Unknown date format: {type(row_date_str)}", flush=True)
                                    continue
                                    
                                # Check if the row is from the last week
                                if row_date >= one_week_ago:
                                    print(f"✅ Processing row for date: {row_date}", flush=True)
                                    
                                    # Create a data point for InfluxDB
                                    point = Point("nutrition_data")
                                    
                                    # Add all fields from the row
                                    for key, value in row_data.items():
                                        # Skip empty values
                                        if value is None or (isinstance(value, str) and not value.strip()):
                                            continue
                                            
                                        if isinstance(value, (int, float)):
                                            point.field(key, value)
                                        else:
                                            # Try to convert to number if possible
                                            try:
                                                # Extract numeric part if it's a string with units
                                                if isinstance(value, str):
                                                    numeric_match = re.search(r'([\d,\.]+)', value)
                                                    if numeric_match:
                                                        numeric_value = float(numeric_match.group(1).replace(',', ''))
                                                        point.field(key, numeric_value)
                                                    else:
                                                        point.tag(key, value)
                                                else:
                                                    point.tag(key, str(value))
                                            except (ValueError, TypeError):
                                                # Keep as tag if conversion fails
                                                point.tag(key, str(value))
                                    
                                    # Use the row date for the timestamp
                                    timestamp = datetime.combine(row_date, datetime.min.time())
                                    point.time(timestamp, WritePrecision.NS)
                                    
                                    data_points.append(point)
                                else:
                                    print(f"⏭️ Skipping row for date: {row_date} (before {one_week_ago})", flush=True)
                            except Exception as date_err:
                                print(f"⚠️ Error processing date: {date_err}", flush=True)
                                continue
                    except Exception as row_err:
                        print(f"⚠️ Error processing row: {row_err}", flush=True)
                        continue
            
            except Exception as xlrd_err:
                print(f"⚠️ Could not use xlrd to read Excel file: {xlrd_err}", flush=True)
                print("Trying alternative method...", flush=True)
                
                # If xlrd fails, try direct CSV reading for XLS
                # (this won't work well but is a fallback)
                try:
                    with open(xls_file_path, 'r', encoding='latin-1') as f:
                        reader = csv.reader(f)
                        rows = list(reader)
                        
                        if rows:
                            headers = rows[0]
                            for row in rows[1:]:
                                row_data = {}
                                for i, value in enumerate(row):
                                    if i < len(headers):
                                        row_data[headers[i]] = value
                                
                                # Now process the row_data similar to above
                                # ... (code similar to xlrd processing)
                                print(f"📊 Processed row with CSV fallback: {row_data}", flush=True)
                        else:
                            print("⚠️ No data found in the CSV fallback", flush=True)
                            
                except Exception as csv_err:
                    print(f"⚠️ CSV fallback also failed: {csv_err}", flush=True)
                    raise Exception("Could not parse the Excel file with any available method")
            
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