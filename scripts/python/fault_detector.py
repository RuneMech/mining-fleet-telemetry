
# fault_detector.py
import pandas as pd
from sqlalchemy import create_engine, text
import os

# ----------------------------
# CONFIG
# ----------------------------
DB_USER = os.environ["TS_DB_USER"]
DB_PASSWORD = os.environ["TS_DB_PASSWORD"]
DB_NAME = os.environ["TS_DB_NAME"]
DB_HOST = os.environ["TS_DB_HOST"]
DB_PORT = int(os.environ.get("TS_DB_PORT", 5432))

TELEMETRY_TABLE = os.getenv("TS_TELEMETRY_TABLE", "engine_telemetry")
FAULT_TABLE = os.getenv("TS_FAULT_TABLE", "fault_events")

DATABASE_URI = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URI)

# Thresholds per subsystem (OEM-style)
THRESHOLDS = {
    "engine_rpm": 1700,
    "coolant_temp_c": 100,
    "oil_temp_c": 105,
    "fuel_rate_lph": 500,
    "hydraulic_pressure_kpa": 25000,
    "turbo_boost_kpa": 260
}

# Minimum duration above threshold to count as a real fault (seconds)
MIN_TIME_OVER_THRESHOLD_SEC = {
    "engine_rpm": 15,
    "coolant_temp_c": 20,
    "oil_temp_c": 20,
    "fuel_rate_lph": 20,
    "hydraulic_pressure_kpa": 5,
    "turbo_boost_kpa": 5
}

# Sampling interval in seconds
SAMPLING_INTERVAL_SEC = 5

# ----------------------------
# MAIN SCRIPT
# ----------------------------
def main():

    # -------------------------------
    # READ TELEMETRY FROM TIMESCALEDB
    # -------------------------------
    print("Querying telemetry data from TimescaleDB...")
    telemetry_df = pd.read_sql(f"SELECT * FROM {TELEMETRY_TABLE};", engine)
    telemetry_df['timestamp'] = pd.to_datetime(telemetry_df['timestamp'])
    print(f"Loaded {len(telemetry_df)} rows of telemetry data.")

    all_faults = []


    # ----------------------------
    # FAULT DETECTION
    # ----------------------------    
    for subsystem, threshold in THRESHOLDS.items():
        min_samples = MIN_TIME_OVER_THRESHOLD_SEC[subsystem] // SAMPLING_INTERVAL_SEC

        for asset_id, truck_df in telemetry_df.groupby('asset_id'):
            truck_df = truck_df.sort_values('timestamp')

            # Filter only samples exceeding threshold
            exceed_df = truck_df[truck_df[subsystem] > threshold]
            if exceed_df.empty:
                continue

            current_event = None
            consecutive_count = 0

            for idx, row in exceed_df.iterrows():
                if current_event is None:
                    # Start new fault event
                    current_event = {
                        "asset_id": asset_id,
                        "subsystem": subsystem,
                        "timestamp_start": row['timestamp'],
                        "timestamp_end": row['timestamp'],
                        "max_value": row[subsystem],
                        "threshold": threshold,
                        "duty_cycle_stage": row['duty_cycle_stage'],
                        "make": row['make']
                    }
                    consecutive_count = 1
                else:
                    prev_end = current_event['timestamp_end']
                    # Check if consecutive (allow gaps up to sampling interval)
                    if (row['timestamp'] - prev_end).total_seconds() <= SAMPLING_INTERVAL_SEC:
                        consecutive_count += 1
                        current_event['timestamp_end'] = row['timestamp']
                        current_event['max_value'] = max(current_event['max_value'], row[subsystem])
                    else:
                        # End previous event
                        if consecutive_count >= min_samples:
                            all_faults.append(current_event)
                        # Start new event
                        current_event = {
                            "asset_id": asset_id,
                            "subsystem": subsystem,
                            "timestamp_start": row['timestamp'],
                            "timestamp_end": row['timestamp'],
                            "max_value": row[subsystem],
                            "threshold": threshold,
                            "duty_cycle_stage": row['duty_cycle_stage'],
                            "make": row['make']
                        }
                        consecutive_count = 1

            # End-of-file: save last event if long enough
            if current_event is not None and consecutive_count >= min_samples:
                all_faults.append(current_event)

    # Build final DataFrame
    faults_df = pd.DataFrame(all_faults)
    faults_df = faults_df.sort_values(by=['asset_id', 'timestamp_start']).reset_index(drop=True)
    print(f"Detected {len(faults_df)} fault events.")
    
    # ----------------------------
    # WRITE FAULTS TO TIMESCALEDB
    # ----------------------------
    with engine.begin() as conn:
        # Drop table if exists (optional for fresh runs)
        conn.execute(text(f"DROP TABLE IF EXISTS {FAULT_TABLE} CASCADE;"))

        # Create table
        conn.execute(text(f"""
            CREATE TABLE {FAULT_TABLE} (
                timestamp_start TIMESTAMP NOT NULL,
                timestamp_end TIMESTAMP NOT NULL,
                asset_id TEXT NOT NULL,
                subsystem TEXT,
                max_value REAL,
                threshold REAL,
                duty_cycle_stage TEXT,
                make TEXT
            );
        """))

        # Convert to hypertable
        conn.execute(text(f"""
            SELECT create_hypertable('{FAULT_TABLE}', 'timestamp_start', if_not_exists => TRUE);
        """))
        
    # Insert DataFrame into DB
    faults_df.to_sql(FAULT_TABLE, engine, if_exists="append", index=False, method="multi")
    print(f"Inserted {len(faults_df)} fault events into TimescaleDB table '{FAULT_TABLE}'.")


if __name__ == "__main__":
    main()
