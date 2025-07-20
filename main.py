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

    # Create a unique temporary directory for Chrome user data
    import tempfile
    temp_dir = tempfile.mkdtemp(prefix="chrome_user_data_")
    
    chrome_options = Options()
    # Re-enable headless mode as this is likely running in a container
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Specify unique user data directory to avoid conflicts
    chrome_options.add_argument(f"--user-data-dir={temp_dir}")
    
    # Add user agent to appear as a regular browser
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")
    
    # Enable cookies for the login process
    chrome_options.add_experimental_option("prefs", {
        # Allow cookies (value 1 allows, 2 blocks)
        "profile.default_content_setting_values.cookies": 1,
        "download.prompt_for_download": False,
        "directory_upgrade": True
    })
    
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
        
        # Save the login form HTML before submitting for comparison
        initial_html = driver.page_source
        
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

        # Try alternate approach - go directly to reports page and see if we're already logged in
        print("🔍 Trying direct navigation to reports page", flush=True)
        driver.get("https://www.mynetdiary.com/reports.do")
        time.sleep(5)  # Wait for redirect if not logged in
        
        # Check if we're on the reports page or were redirected to login
        print(f"🌐 URL after direct navigation: {driver.current_url}", flush=True)
        
        direct_nav_screenshot = f"/app/downloads/direct_nav_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        driver.save_screenshot(direct_nav_screenshot)
        print(f"🖼 Screenshot after direct navigation: {direct_nav_screenshot}", flush=True)
        
        # Check if we're on reports page or login page
        if "reports.do" in driver.current_url:
            print("✅ Successfully reached reports page directly", flush=True)
        else:
            print("⚠️ Redirected from reports page, may need to log in again", flush=True)
            # We're likely at the login page again, retry login
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
            
            # Try direct navigation again
            driver.get("https://www.mynetdiary.com/reports.do")
            time.sleep(3)

        # --- REPORT PAGE ---
        print("📊 Opening reports page", flush=True)
        
        # Save screenshot of what should be the reports page
        reports_screenshot = f"/app/downloads/reports_page_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        driver.save_screenshot(reports_screenshot)
        print(f"🖼 Reports page screenshot: {reports_screenshot}", flush=True)

        # Continue with reports page interaction
        try:
            # Set form fields in the correct order with delays between each
            
            # 1. Wait for the period dropdown to be present and select "Select dates"
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "lstPeriodOptions")))
            period_select = Select(driver.find_element(By.ID, "lstPeriodOptions"))
            period_select.select_by_value("periodCustom")
            print("📅 Set Period to 'Select dates'", flush=True)
            time.sleep(1)  # Wait for the date fields to appear
            
            # 2. Set Report Type to "Food Report" (it should be the default, but set it explicitly)
            details_select = Select(driver.find_element(By.ID, "lstDetails"))
            details_select.select_by_value("allFoods")
            print("📊 Set Report Type to 'Food Report'", flush=True)
            time.sleep(1)
            
            # 3. Set Nutrient Options to "Tracked Nutrients" (it should be the default, but set it explicitly)
            nutrients_select = Select(driver.find_element(By.ID, "lstNutrients"))
            nutrients_select.select_by_value("trackedNutrients")
            print("🥗 Set Nutrient Options to 'Tracked Nutrients'", flush=True)
            time.sleep(1)
            
            # 4. Calculate yesterday's date (since the script runs at 2:00 AM)
            yesterday = (date.today() - timedelta(days=1)).strftime("%d/%m/%Y")
            
            # 5. Handle the date fields with calendar button clicks
            # For startDate (From)
            try:
                # Click the calendar button for the start date
                start_cal_button = driver.find_element(By.XPATH, "//div[@id='startDateDiv']//button")
                driver.execute_script("arguments[0].click();", start_cal_button)
                print("📅 Clicked start date calendar button", flush=True)
                time.sleep(1)
                
                # Now the datepicker should be visible, find and click yesterday's date
                # This assumes the calendar opens to the current month with yesterday visible
                # You might need to adjust this logic if the calendar UI is different
                
                # Try to find the day element with yesterday's day number
                yesterday_day = (date.today() - timedelta(days=1)).day
                day_element = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, f"//td[contains(@class, 'day') and text()='{yesterday_day}']"))
                )
                driver.execute_script("arguments[0].click();", day_element)
                print(f"📅 Selected day {yesterday_day} in calendar for start date", flush=True)
                time.sleep(1)
            except Exception as start_date_err:
                print(f"⚠️ Could not set start date via calendar: {start_date_err}", flush=True)
                # Fallback to JavaScript for start date
                try:
                    driver.execute_script(f"document.getElementById('startDate').value = '{yesterday}'")
                    print(f"📅 Set start date with JavaScript: {yesterday}", flush=True)
                except Exception as js_err:
                    print(f"❌ Failed to set start date: {js_err}", flush=True)
            
            # For endDate (To) - also set to yesterday
            try:
                # Click the calendar button for the end date
                end_cal_button = driver.find_element(By.XPATH, "//div[@id='endDateDiv']//button")
                driver.execute_script("arguments[0].click();", end_cal_button)
                print("📅 Clicked end date calendar button", flush=True)
                time.sleep(1)
                
                # Find and click yesterday's date again
                day_element = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, f"//td[contains(@class, 'day') and text()='{yesterday_day}']"))
                )
                driver.execute_script("arguments[0].click();", day_element)
                print(f"📅 Selected day {yesterday_day} in calendar for end date", flush=True)
                time.sleep(1)
            except Exception as end_date_err:
                print(f"⚠️ Could not set end date via calendar: {end_date_err}", flush=True)
                # Fallback to JavaScript for end date
                try:
                    driver.execute_script(f"document.getElementById('endDate').value = '{yesterday}'")
                    print(f"📅 Set end date with JavaScript: {yesterday}", flush=True)
                except Exception as js_err:
                    print(f"❌ Failed to set end date: {js_err}", flush=True)
            
            # Take a screenshot after setting all form fields
            form_filled_screenshot = f"/app/downloads/form_filled_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
            driver.save_screenshot(form_filled_screenshot)
            print(f"🖼 Form filled screenshot: {form_filled_screenshot}", flush=True)
            
            # Wait for the report to load after all fields are set
            print("⏳ Waiting for report to update after form completion...", flush=True)
            time.sleep(5)  # Initial wait for JavaScript processing
            
            # Wait for report table to be present
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.report"))
            )
            
            # Additional wait for table content to fully load
            time.sleep(3)
            
            print("✅ Report table loaded", flush=True)
            
            # Take a screenshot of the loaded report
            loaded_report_screenshot = f"/app/downloads/loaded_report_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
            driver.save_screenshot(loaded_report_screenshot)
            print(f"🖼 Loaded report screenshot: {loaded_report_screenshot}", flush=True)
            
            # Parse report data and write to InfluxDB
            try:
                print("📊 Parsing report data", flush=True)
                
                # Find the report table
                report_table = driver.find_element(By.CSS_SELECTOR, "table.report")
                
                # Extract table headers
                headers = []
                header_cells = report_table.find_elements(By.CSS_SELECTOR, "thead th")
                for cell in header_cells:
                    headers.append(cell.text.strip())
                
                print(f"📋 Found headers: {headers}", flush=True)
                
                # Extract table rows
                rows = report_table.find_elements(By.CSS_SELECTOR, "tbody tr")
                print(f"📋 Found {len(rows)} data rows", flush=True)
                
                # Process data rows
                data_points = []
                
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    row_data = {}
                    
                    # Skip empty rows
                    if len(cells) < 2:
                        continue
                    
                    # Extract data from each cell
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            row_data[headers[i]] = cell.text.strip()
                    
                    # Create a data point for InfluxDB
                    if 'Date' in row_data:
                        try:
                            # Parse date from the report (assuming format like MM/DD/YYYY)
                            # Adjust format as needed based on actual data
                            date_str = row_data['Date']
                            
                            # Create an InfluxDB point
                            point = Point("nutrition_data")
                            
                            # Add timestamp (convert to proper format for InfluxDB)
                            try:
                                # Try different date formats
                                try:
                                    # MM/DD/YYYY format
                                    timestamp = datetime.strptime(date_str, "%m/%d/%Y")
                                except ValueError:
                                    try:
                                        # DD/MM/YYYY format
                                        timestamp = datetime.strptime(date_str, "%d/%m/%Y")
                                    except ValueError:
                                        # YYYY-MM-DD format
                                        timestamp = datetime.strptime(date_str, "%Y-%m-%d")
                            except Exception as date_err:
                                print(f"⚠️ Could not parse date '{date_str}': {date_err}", flush=True)
                                # Use current time as fallback
                                timestamp = datetime.utcnow()
                            
                            point.time(timestamp, WritePrecision.NS)
                            
                            # Add all other fields as tags or fields
                            for key, value in row_data.items():
                                if key == 'Date':
                                    continue  # Already used for timestamp
                                
                                # Try to convert numeric values
                                try:
                                    # Remove any non-numeric characters (like commas or units)
                                    clean_value = ''.join(c for c in value if c.isdigit() or c == '.' or c == '-')
                                    if clean_value:
                                        # Try to convert to float
                                        numeric_value = float(clean_value)
                                        point.field(key, numeric_value)
                                    else:
                                        # Keep as string if not numeric
                                        point.tag(key, value)
                                except ValueError:
                                    # Keep as string if conversion fails
                                    point.tag(key, value)
                            
                            data_points.append(point)
                        except Exception as point_err:
                            print(f"⚠️ Error creating data point: {point_err}", flush=True)
                
                print(f"📊 Created {len(data_points)} data points", flush=True)
                
                # Write to InfluxDB if configuration exists
                if INFLUX_URL and INFLUX_TOKEN and INFLUX_ORG and INFLUX_BUCKET:
                    print(f"💾 Writing data to InfluxDB at {INFLUX_URL}", flush=True)
                    
                    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
                    write_api = client.write_api()
                    
                    # Write all data points
                    write_api.write(bucket=INFLUX_BUCKET, record=data_points)
                    write_api.close()
                    
                    print(f"✅ Successfully wrote {len(data_points)} data points to InfluxDB", flush=True)
                else:
                    print("⚠️ InfluxDB configuration missing, skipping data upload", flush=True)
                    
            except Exception as parsing_err:
                print(f"❌ Error parsing or uploading report data: {parsing_err}", flush=True)
                # Take a screenshot of the report page for debugging
                report_error_screenshot = f"/app/downloads/report_error_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
                driver.save_screenshot(report_error_screenshot)
                print(f"🖼 Report error screenshot: {report_error_screenshot}", flush=True)
                # Don't raise the exception to allow cleanup to continue
        except Exception as report_err:
            print(f"❌ Error interacting with reports page: {report_err}", flush=True)
            report_err_screenshot = f"/app/downloads/report_interaction_error_{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
            driver.save_screenshot(report_err_screenshot)
            print(f"🖼 Report interaction error screenshot: {report_err_screenshot}", flush=True)

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

# Run once to avoid parallel execution
run_job()

# Schedule 2am daily (but don't run immediately again)
schedule.every().day.at("02:00").do(run_job)
print("📆 Scheduled daily run at 02:00", flush=True)

# Add a short delay before entering the main loop
time.sleep(5)

while True:
    schedule.run_pending()
    time.sleep(30)