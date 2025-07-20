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
                
                # Extract table headers - the headers in this table are in a special format with rotated text
                headers = []
                try:
                    # First try to get the rotated headers which are in <span class="rotate"> inside <td class="rotatedTd">
                    header_cells = report_table.find_elements(By.CSS_SELECTOR, "thead tr td.rotatedTd span.rotate")
                    for cell in header_cells:
                        # Clean up the header text (remove non-breaking spaces and commas)
                        header_text = cell.text.strip().replace('\xa0', ' ').split(',')[0]
                        headers.append(header_text)
                    
                    # Add the "Time" header which is in a different format
                    time_header = report_table.find_element(By.CSS_SELECTOR, "thead tr td[style*='vertical-align: bottom']")
                    if time_header.text.strip():
                        headers.append(time_header.text.strip())
                    
                    print(f"📋 Found rotated headers: {headers}", flush=True)
                except Exception as rotated_err:
                    print(f"⚠️ Error finding rotated headers: {rotated_err}", flush=True)
                    
                    # Fallback: Try to extract header titles from the title attributes
                    try:
                        header_cells = report_table.find_elements(By.CSS_SELECTOR, "thead tr td[title]")
                        for cell in header_cells:
                            title = cell.get_attribute("title")
                            if title and "column" in title:
                                # Extract nutrient name from title like "Calories column"
                                nutrient = title.replace(" column", "").strip()
                                headers.append(nutrient)
                        
                        print(f"📋 Found headers from title attributes: {headers}", flush=True)
                    except Exception as title_err:
                        print(f"⚠️ Error finding headers from titles: {title_err}", flush=True)
                
                # If still no headers, use default headers based on the table structure
                if not headers:
                    print("⚠️ Using default headers based on table structure", flush=True)
                    headers = ["Date", "Calories", "Total Fat", "Carbs", "Protein", "Sat. Fat", 
                               "Trans Fat", "Net Carbs", "Fiber", "Sodium", "Calcium", "Time"]
                
                print(f"📋 Final headers list: {headers}", flush=True)
                
                # Extract data rows - focus on the daily information row
                try:
                    # Look for rows with class "day" which contain the daily summary
                    day_rows = report_table.find_elements(By.CSS_SELECTOR, "tbody tr.day")
                    print(f"📋 Found {len(day_rows)} day summary rows", flush=True)
                    
                    # Process each day row
                    data_points = []
                    
                    for day_row in day_rows:
                        row_data = {}
                        
                        # Extract the date from the h4 element in the first column
                        try:
                            date_element = day_row.find_element(By.CSS_SELECTOR, "h4")
                            date_text = date_element.text.strip()
                            # Parse something like "Saturday, Jul 19" into a date
                            print(f"📅 Found date text: {date_text}", flush=True)
                            
                            # Add the year which is in the URL parameter
                            try:
                                link_element = day_row.find_element(By.CSS_SELECTOR, "a.dailyReportLink")
                                href = link_element.get_attribute("href")
                                if "date=" in href:
                                    date_param = href.split("date=")[1].split("&")[0]
                                    if len(date_param) == 8:  # Format: YYYYMMDD
                                        year = date_param[:4]
                                        month = date_param[4:6]
                                        day = date_param[6:8]
                                        full_date = f"{year}-{month}-{day}"
                                        row_data["Date"] = full_date
                                        print(f"📅 Extracted full date from link: {full_date}", flush=True)
                            except Exception as link_err:
                                print(f"⚠️ Error extracting date from link: {link_err}", flush=True)
                                row_data["Date"] = date_text
                        except Exception as date_err:
                            print(f"⚠️ Error extracting date: {date_err}", flush=True)
                            # Use yesterday's date as fallback
                            row_data["Date"] = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
                        
                        # Extract nutrient data from the cells
                        cells = day_row.find_elements(By.CSS_SELECTOR, "td.numeric")
                        print(f"📋 Found {len(cells)} numeric cells in day row", flush=True)
                        
                        for i, cell in enumerate(cells):
                            if i < len(headers) - 1:  # Skip Time which isn't in the day summary
                                # Clean up the text: remove 'cals', 'g', 'mg', etc.
                                value_text = cell.text.strip()
                                
                                # Print raw value for debugging
                                print(f"📊 Raw value for {headers[i]}: '{value_text}'", flush=True)
                                
                                # Extract numeric value
                                import re
                                # Match numbers including commas and decimals
                                numeric_match = re.search(r'([\d,\.]+)', value_text)
                                if numeric_match:
                                    value = numeric_match.group(1).replace(',', '')
                                    try:
                                        row_data[headers[i]] = float(value)
                                    except ValueError:
                                        row_data[headers[i]] = value_text
                                else:
                                    row_data[headers[i]] = value_text
                        
                        print(f"📊 Extracted row data: {row_data}", flush=True)
                        
                        # Create InfluxDB point
                        if row_data and "Date" in row_data:
                            try:
                                point = Point("nutrition_data")
                                
                                # Parse the date
                                try:
                                    # Try different date formats
                                    if "-" in row_data["Date"]:
                                        # YYYY-MM-DD format
                                        timestamp = datetime.strptime(row_data["Date"], "%Y-%m-%d")
                                    elif "/" in row_data["Date"]:
                                        # Try both MM/DD/YYYY and DD/MM/YYYY
                                        try:
                                            timestamp = datetime.strptime(row_data["Date"], "%m/%d/%Y")
                                        except ValueError:
                                            timestamp = datetime.strptime(row_data["Date"], "%d/%m/%Y")
                                    else:
                                        # Try to parse text format like "Saturday, Jul 19"
                                        month_abbr = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                                                     "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
                                        
                                        parts = row_data["Date"].split(", ")[1].split(" ")
                                        if len(parts) == 2:
                                            month = month_abbr.get(parts[0], 1)
                                            day = int(parts[1])
                                            year = date.today().year
                                            timestamp = datetime(year, month, day)
                                except Exception as date_parse_err:
                                    print(f"⚠️ Could not parse date '{row_data['Date']}': {date_parse_err}", flush=True)
                                    timestamp = datetime.utcnow()
                                
                                point.time(timestamp, WritePrecision.NS)
                                
                                # Add all other fields
                                for key, value in row_data.items():
                                    if key == "Date":
                                        continue  # Already used for timestamp
                                    
                                    if isinstance(value, (int, float)):
                                        point.field(key, value)
                                    else:
                                        # Convert string to number if possible
                                        try:
                                            # Remove any non-numeric characters (like commas or units)
                                            clean_value = ''.join(c for c in str(value) if c.isdigit() or c == '.' or c == '-')
                                            if clean_value:
                                                numeric_value = float(clean_value)
                                                point.field(key, numeric_value)
                                            else:
                                                # Keep as string if not numeric
                                                point.tag(key, str(value))
                                        except ValueError:
                                            # Keep as string if conversion fails
                                            point.tag(key, str(value))
                                
                                data_points.append(point)
                                print(f"📊 Created data point for date: {row_data['Date']}", flush=True)
                            except Exception as point_err:
                                print(f"⚠️ Error creating data point: {point_err}", flush=True)
                    
                except Exception as day_row_err:
                    print(f"❌ Error processing day rows: {day_row_err}", flush=True)
                    
                print(f"📊 Created {len(data_points)} data points", flush=True)
                
                # Write to InfluxDB if configuration exists
                if INFLUX_URL and INFLUX_TOKEN and INFLUX_ORG and INFLUX_BUCKET:
                    print(f"💾 Writing data to InfluxDB at {INFLUX_URL}", flush=True)
                    print(f"💾 Org: {INFLUX_ORG}, Bucket: {INFLUX_BUCKET}", flush=True)
                    print(f"💾 Token: {INFLUX_TOKEN[:5]}...{INFLUX_TOKEN[-5:]}", flush=True)
                    
                    try:
                        # Verify connection first
                        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
                        health = client.health()
                        print(f"💾 InfluxDB connection health: {health.status}", flush=True)
                        
                        # Check if bucket exists
                        buckets_api = client.buckets_api()
                        try:
                            bucket = buckets_api.find_bucket_by_name(INFLUX_BUCKET)
                            if bucket:
                                print(f"💾 Found bucket: {INFLUX_BUCKET}", flush=True)
                            else:
                                print(f"⚠️ Bucket not found: {INFLUX_BUCKET}", flush=True)
                        except Exception as bucket_err:
                            print(f"⚠️ Error checking bucket: {bucket_err}", flush=True)
                        
                        # Now write the data
                        write_api = client.write_api()
                        
                        # Log a sample of what we're writing
                        if data_points:
                            sample_point = data_points[0]
                            print(f"💾 Sample point: {sample_point}", flush=True)
                        
                        # Write all data points
                        write_api.write(bucket=INFLUX_BUCKET, record=data_points)
                        write_api.close()
                        
                        print(f"✅ Successfully wrote {len(data_points)} data points to InfluxDB", flush=True)
                        
                        # Verify points were written by querying
                        query_api = client.query_api()
                        try:
                            yesterday_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
                            query = f'from(bucket:"{INFLUX_BUCKET}") |> range(start: {yesterday_date}T00:00:00Z, stop: {yesterday_date}T23:59:59Z) |> filter(fn: (r) => r._measurement == "nutrition_data") |> limit(n:1)'
                            
                            result = query_api.query(query=query)
                            
                            if result and len(result) > 0:
                                print(f"✅ Verified data was written - found {len(result)} records", flush=True)
                            else:
                                print("⚠️ Could not verify data was written - query returned no results", flush=True)
                        except Exception as query_err:
                            print(f"⚠️ Error verifying data write: {query_err}", flush=True)
                        
                        client.close()
                    except Exception as influx_err:
                        print(f"❌ InfluxDB error: {influx_err}", flush=True)
                        print(f"❌ InfluxDB error type: {type(influx_err)}", flush=True)
                        traceback.print_exc()
                else:
                    missing = []
                    if not INFLUX_URL:
                        missing.append("INFLUX_URL")
                    if not INFLUX_TOKEN:
                        missing.append("INFLUX_TOKEN")
                    if not INFLUX_ORG:
                        missing.append("INFLUX_ORG")
                    if not INFLUX_BUCKET:
                        missing.append("INFLUX_BUCKET")
                    
                    print(f"⚠️ InfluxDB configuration missing: {', '.join(missing)}", flush=True)
                    
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