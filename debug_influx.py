#!/usr/bin/env python3

import os
from influxdb_client import InfluxDBClient
import sys

# InfluxDB v2 config (set these as environment variables)
INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")

def check_measurements():
    """List all measurements in the bucket and their count"""
    if not all([INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET]):
        print("❌ Error: Environment variables not set properly")
        print("   Please set INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET")
        return False
    
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query_api = client.query_api()
        
        # Query to get all measurements
        query = f'''
        import "influxdata/influxdb/schema"
        
        schema.measurements(bucket: "{INFLUX_BUCKET}")
        '''
        
        result = query_api.query(query)
        
        measurements = []
        for table in result:
            for record in table.records:
                measurements.append(record.values["_value"])
        
        print(f"📊 Found {len(measurements)} measurements in bucket '{INFLUX_BUCKET}':")
        
        for measurement in measurements:
            # Count points in each measurement
            count_query = f'''
            from(bucket: "{INFLUX_BUCKET}")
                |> range(start: -30d)
                |> filter(fn: (r) => r._measurement == "{measurement}")
                |> count()
                |> yield(name: "count")
            '''
            
            count_result = query_api.query(count_query)
            count = 0
            for table in count_result:
                for record in table.records:
                    count = record.get_value()
            
            print(f"   - {measurement}: {count} points")
        
        return True
        
    except Exception as e:
        print(f"❌ Error connecting to InfluxDB: {e}")
        return False

def run_debug_script():
    """Run the debug_influx.py script"""
    try:
        import subprocess
        result = subprocess.run([sys.executable, "debug_influx.py"], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Error running debug script: {result.stderr}")
        else:
            print("✅ Debug script executed successfully:")
            print(result.stdout)
    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    if check_measurements():
        run_debug_script()
