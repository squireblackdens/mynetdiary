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
import pandas as pd

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
            # Get the date from one week ago
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
                
                # Find the index of the 'Date & Time' column
                date_time_idx = -1
                meal_idx = -1
                for idx, header in enumerate(headers):
                    if header.strip() == 'Date & Time':
                        date_time_idx = idx
                    elif header.strip() == 'Meal':
                        meal_idx = idx
                
                if date_time_idx == -1:
                    print("⚠️ Could not find 'Date & Time' column in the Excel file", flush=True)
                    raise Exception("Missing 'Date & Time' column")
                
                if meal_idx == -1:
                    print("⚠️ Could not find 'Meal' column in the Excel file", flush=True)
                    raise Exception("Missing 'Meal' column")
                
                # Group data points by meal type
                meal_data = {}
                recent_entries = 0
                
                # Process rows
                for row_idx in range(1, sheet.nrows):
                    try:
                        # Get date/time value
                        date_time_val = sheet.cell_value(row_idx, date_time_idx)
                        meal_val = sheet.cell_value(row_idx, meal_idx)
                        
                        # Parse the date/time
                        if isinstance(date_time_val, str):
                            # Try different date formats (MyNetDiary format is typically MM/DD/YYYY hh:mm)
                            try:
                                # Try with time component
                                date_time_obj = datetime.strptime(date_time_val, '%m/%d/%Y %H:%M')
                            except ValueError:
                                try:
                                    # Try just the date part
                                    date_time_obj = datetime.strptime(date_time_val, '%m/%d/%Y')
                                except ValueError:
                                    print(f"⚠️ Could not parse date string: {date_time_val}", flush=True)
                                    continue
                        elif isinstance(date_time_val, float):
                            # Handle Excel date (float days since 1900-01-01)
                            # Get the integer part (days) and fractional part (time)
                            days = int(date_time_val)
                            frac_of_day = date_time_val - days
                            
                            # Excel dates start from 1900-01-01, with 1 = 1900-01-01
                            # But there's a leap year bug, so we use 1899-12-30 as base
                            base_date = datetime(1899, 12, 30)
                            
                            # Add days and convert fractional day to hours/minutes
                            date_time_obj = base_date + timedelta(days=days)
                            
                            # Add time component (frac_of_day * 24 hours * 60 minutes * 60 seconds)
                            seconds = int(frac_of_day * 86400)  # 86400 = 24*60*60
                            date_time_obj += timedelta(seconds=seconds)
                        else:
                            print(f"⚠️ Unknown date format: {type(date_time_val)}", flush=True)
                            continue
                        
                        # Extract just the date part for comparison
                        entry_date = date_time_obj.date()
                        
                        # Check if this entry is from the last week
                        if entry_date >= one_week_ago:
                            recent_entries += 1
                            
                            # Create a row data dictionary with all fields
                            row_data = {}
                            for col_idx in range(sheet.ncols):
                                if col_idx < len(headers):
                                    cell_value = sheet.cell_value(row_idx, col_idx)
                                    header = headers[col_idx]
                                    row_data[header] = cell_value
                            
                            # Add to the appropriate meal group
                            if meal_val not in meal_data:
                                meal_data[meal_val] = []
                            
                            # Store the row data and the parsed datetime
                            meal_data[meal_val].append({
                                'data': row_data,
                                'datetime': date_time_obj
                            })
                    except Exception as row_err:
                        print(f"⚠️ Error processing row {row_idx}: {row_err}", flush=True)
                        continue
                
                print(f"✅ Found {recent_entries} entries from the last week", flush=True)
                
                # Create InfluxDB points for each meal group
                for meal_name, entries in meal_data.items():
                    print(f"📊 Processing {len(entries)} entries for meal: {meal_name}", flush=True)
                    
                    for entry in entries:
                        row_data = entry['data']
                        timestamp = entry['datetime']
                        
                        # Create a data point with meal as a tag
                        point = Point("nutrition_data")
                        point.tag("meal", meal_name)
                        
                        # Add all numeric fields from the row
                        for key, value in row_data.items():
                            # Skip the meal field since we're using it as a tag
                            if key == 'Meal':
                                continue
                                
                            # Skip empty values
                            if value is None or (isinstance(value, str) and not value.strip()):
                                continue
                            
                            # Clean the field name for InfluxDB (remove commas, units, etc.)
                            clean_key = re.sub(r',\s*\w+$', '', key).strip()
                            
                            if isinstance(value, (int, float)) and not isinstance(value, bool):
                                # Direct numeric value
                                point.field(clean_key, float(value))
                            elif isinstance(value, str):
                                # Try to extract numeric part if it has units
                                numeric_match = re.search(r'^([\d\.]+)', value.strip())
                                if numeric_match:
                                    try:
                                        numeric_value = float(numeric_match.group(1))
                                        point.field(clean_key, numeric_value)
                                    except (ValueError, TypeError):
                                        # If conversion fails, add as a tag
                                        point.tag(clean_key, value)
                                else:
                                    # Non-numeric string becomes a tag
                                    point.tag(clean_key, value)
                            else:
                                # Other types become string tags
                                point.tag(clean_key, str(value))
                        
                        # Add food name as a tag for easier querying
                        if 'Name' in row_data:
                            point.tag("food_name", str(row_data['Name']))
                        
                        # Use the parsed timestamp for the data point
                        point.time(timestamp, WritePrecision.NS)
                        data_points.append(point)
                
            except Exception as xlrd_err:
                print(f"⚠️ Error using xlrd to process Excel file: {xlrd_err}", flush=True)
                
                # Try pandas as a fallback
                try:
                    print("🔄 Trying pandas for Excel processing...", flush=True)
                    df = pd.read_excel(xls_file_path)
                    
                    # Convert 'Date & Time' column to datetime
                    if 'Date & Time' in df.columns:
                        df['Date & Time'] = pd.to_datetime(df['Date & Time'], errors='coerce')
                        
                        # Filter to only include entries from the last week
                        one_week_ago_pd = pd.Timestamp(one_week_ago)
                        recent_df = df[df['Date & Time'] >= one_week_ago_pd]
                        
                        print(f"✅ Found {len(recent_df)} entries from the last week using pandas", flush=True)
                        
                        # Group by meal
                        if 'Meal' in df.columns:
                            meal_groups = recent_df.groupby('Meal')
                            
                            for meal_name, meal_group in meal_groups:
                                print(f"📊 Processing {len(meal_group)} entries for meal: {meal_name}", flush=True)
                                
                                for _, row in meal_group.iterrows():
                                    # Create a data point with meal as a tag
                                    point = Point("nutrition_data")
                                    point.tag("meal", meal_name)
                                    
                                    # Add fields and tags
                                    for col in row.index:
                                        value = row[col]
                                        
                                        # Skip null values and meal (already used as tag)
                                        if pd.isna(value) or col == 'Meal':
                                            continue
                                        
                                        # Clean column name
                                        clean_col = re.sub(r',\s*\w+$', '', col).strip()
                                        
                                        # Handle different data types
                                        if pd.api.types.is_numeric_dtype(type(value)):
                                            point.field(clean_col, float(value))
                                        else:
                                            # Try to extract numeric part from strings
                                            if isinstance(value, str):
                                                numeric_match = re.search(r'^([\d\.]+)', value.strip())
                                                if numeric_match:
                                                    try:
                                                        numeric_value = float(numeric_match.group(1))
                                                        point.field(clean_col, numeric_value)
                                                    except (ValueError, TypeError):
                                                        point.tag(clean_col, str(value))
                                                else:
                                                    point.tag(clean_col, str(value))
                                            else:
                                                point.tag(clean_col, str(value))
                                    
                                    # Add food name as a tag
                                    if 'Name' in row:
                                        point.tag("food_name", str(row['Name']))
                                    
                                    # Set timestamp
                                    timestamp = row['Date & Time']
                                    point.time(timestamp.to_pydatetime(), WritePrecision.NS)
                                    
                                    data_points.append(point)
                        else:
                            print("⚠️ No 'Meal' column found in pandas dataframe", flush=True)
                    else:
                        print("⚠️ No 'Date & Time' column found in pandas dataframe", flush=True)
                    
                except Exception as pd_err:
                    print(f"⚠️ Pandas processing also failed: {pd_err}", flush=True)
                    raise Exception("Could not process Excel file with any available method")
            
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