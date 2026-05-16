
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
from sqlalchemy import create_engine, TIMESTAMP, text
import os

# ----------------------------
# CONFIG
# ----------------------------
FLEET_CSV = os.getenv(
    "FLEET_CSV_PATH",
    "/opt/airflow/data/asset_metadata.csv"
)

# TimescaleDB connection
DB_USER = os.environ["TS_DB_USER"]
DB_PASSWORD = os.environ["TS_DB_PASSWORD"]
DB_NAME = os.environ["TS_DB_NAME"]
DB_HOST = os.environ["TS_DB_HOST"]
DB_PORT = int(os.environ.get("TS_DB_PORT", 5432))  # 5432 is the container port

TABLE_NAME = "engine_telemetry"

DATABASE_URI = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URI)

# Duty-cycle stages
DUTY_CYCLE = ["LOAD", "HAUL", "DUMP", "RETURN", "IDLE"]
SAMPLING_INTERVAL_SEC = 5  # 0.2 Hz

# Stage duration ranges (seconds)
STAGE_DURATION_RANGES = {
    "LOAD": (300, 600),
    "HAUL": (600, 1200),
    "DUMP": (120, 300),
    "RETURN": (600, 1200),
    "IDLE": (60, 300)
}

# Sensor ranges per stage (OEM-accurate)
SENSOR_RANGES = {
    "LOAD":       {"rpm": (1500, 1700), "load_pct": (80, 100), "coolant_c": (85, 95),
                   "oil_c": (90, 100), "fuel_lph": (450, 500), "hydraulic_bar": (200, 250),
                   "turbo_psi": (25, 35), "battery_v": (25, 27)},
    "HAUL":       {"rpm": (1200, 1400), "load_pct": (50, 80), "coolant_c": (80, 90),
                   "oil_c": (85, 95), "fuel_lph": (300, 400), "hydraulic_bar": (150, 200),
                   "turbo_psi": (15, 25), "battery_v": (25, 27)},
    "DUMP":       {"rpm": (1400, 1600), "load_pct": (70, 95), "coolant_c": (85, 95),
                   "oil_c": (90, 100), "fuel_lph": (400, 500), "hydraulic_bar": (180, 220),
                   "turbo_psi": (20, 30), "battery_v": (25, 27)},
    "RETURN":     {"rpm": (1000, 1300), "load_pct": (30, 60), "coolant_c": (75, 85),
                   "oil_c": (80, 90), "fuel_lph": (150, 300), "hydraulic_bar": (100, 150),
                   "turbo_psi": (10, 20), "battery_v": (25, 27)},
    "IDLE":       {"rpm": (600, 750), "load_pct": (0, 10), "coolant_c": (70, 80),
                   "oil_c": (75, 85), "fuel_lph": (50, 120), "hydraulic_bar": (0, 30),
                   "turbo_psi": (0, 5), "battery_v": (24, 26)}
}

SPIKE_CHANCE = 0.03  # 3% chance per subsystem per stage
SPIKE_MAGNITUDE = (1.05, 1.20)  # 5–20% above OEM max
TOTAL_OPERATION_HOURS = 10  # total operational hours per asset
TOTAL_OPERATION_SECONDS = TOTAL_OPERATION_HOURS * 3600

# ----------------------------
# HELPER FUNCTIONS
# ----------------------------
def convert_bar_to_kpa(bar_value):
    return bar_value * 100

def convert_psi_to_kpa(psi_value):
    return psi_value * 6.89476

def generate_sensor_value(stage, sensor):
    low, high = SENSOR_RANGES[stage][sensor]
    return round(random.uniform(low, high), 2)

def generate_spike(stage, sensor):
    _, high = SENSOR_RANGES[stage][sensor]
    return round(high * random.uniform(*SPIKE_MAGNITUDE), 2)

def generate_stage_duration(stage):
    low, high = STAGE_DURATION_RANGES[stage]
    return random.randint(low, high)

# ----------------------------
# MAIN SCRIPT
# ----------------------------
def main():
    print(f"Reading fleet metadata from: {FLEET_CSV}")
    print(f"Connecting to TimescaleDB at: {DB_HOST}:{DB_PORT}, DB: {DB_NAME}")
    
    if not os.path.exists(FLEET_CSV):
        raise FileNotFoundError(f"Asset metadata not found at {FLEET_CSV}")
    fleet_df = pd.read_csv(FLEET_CSV)
    all_rows = []

    for _, truck in fleet_df.iterrows():
        asset_id = truck["asset_id"]
        make = truck["make"]
        num_cycles = random.randint(10, 14)

        # Generate stage durations for all cycles first
        all_stage_durations = []
        for cycle_num in range(num_cycles):
            cycle_durations = [generate_stage_duration(stage) for stage in DUTY_CYCLE]
            all_stage_durations.append(cycle_durations)
        
        # Flatten to compute total duration
        flat_durations = [dur for cycle in all_stage_durations for dur in cycle]
        total_duration = sum(flat_durations)

        # Compute scaling factor to make total operation = TOTAL_OPERATION_SECONDS
        scale_factor = TOTAL_OPERATION_SECONDS / total_duration

        # Apply scaling and round to nearest second
        scaled_durations = [int(d * scale_factor) for d in flat_durations]

        # Create a flattened stage list for iteration
        flat_stages = DUTY_CYCLE * num_cycles

        start_time = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)

        for stage, duration_sec, cycle_num in zip(flat_stages, scaled_durations, 
                                                  [c for c in range(1, num_cycles + 1) for _ in DUTY_CYCLE]):
            num_samples = max(1, duration_sec // SAMPLING_INTERVAL_SEC)

            # Determine spike indices
            spike_indices = {}
            for subsystem in SENSOR_RANGES[stage].keys():
                if random.random() < SPIKE_CHANCE:
                    spike_indices[subsystem] = random.randint(0, num_samples - 1)

            for sample_idx in range(num_samples):
                ts = start_time + timedelta(seconds=sample_idx * SAMPLING_INTERVAL_SEC)
                vals = {}
                for subsystem in SENSOR_RANGES[stage].keys():
                    if subsystem in spike_indices and spike_indices[subsystem] == sample_idx:
                        val = generate_spike(stage, subsystem)
                    else:
                        val = generate_sensor_value(stage, subsystem)
                    vals[subsystem] = val

                # Convert units
                vals["hydraulic_pressure_kpa"] = convert_bar_to_kpa(vals.pop("hydraulic_bar"))
                vals["turbo_boost_kpa"] = convert_psi_to_kpa(vals.pop("turbo_psi"))

                row = {
                    "timestamp": ts,
                    "asset_id": asset_id,
                    "make": make,
                    "engine_rpm": vals["rpm"],
                    "engine_load_pct": vals["load_pct"],
                    "coolant_temp_c": vals["coolant_c"],
                    "oil_temp_c": vals["oil_c"],
                    "fuel_rate_lph": vals["fuel_lph"],
                    "battery_voltage_v": vals["battery_v"],
                    "hydraulic_pressure_kpa": vals["hydraulic_pressure_kpa"],
                    "turbo_boost_kpa": vals["turbo_boost_kpa"],
                    "duty_cycle_stage": stage,
                    "cycle_number": cycle_num
                }
                all_rows.append(row)

            start_time += timedelta(seconds=duration_sec)

    telemetry_df = pd.DataFrame(all_rows)

    # ----------------------------
    # TIMESCALEDB INSERTION
    # ----------------------------
    try:
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {TABLE_NAME} CASCADE"))
            conn.execute(text(f"""
            CREATE TABLE {TABLE_NAME} (
                timestamp TIMESTAMP NOT NULL,
                asset_id TEXT NOT NULL,
                make TEXT,
                engine_rpm INTEGER,
                engine_load_pct INTEGER,
                coolant_temp_c REAL,
                oil_temp_c REAL,
                fuel_rate_lph REAL,
                battery_voltage_v REAL,
                hydraulic_pressure_kpa REAL,
                turbo_boost_kpa REAL,
                duty_cycle_stage TEXT,
                cycle_number INTEGER
            );
            """))
            conn.execute(text(f"""
            SELECT create_hypertable('{TABLE_NAME}', 'timestamp', if_not_exists => TRUE);
            """))

        telemetry_df.to_sql(TABLE_NAME, engine, if_exists="append", index=False, method="multi")
        print(f"Inserted {len(telemetry_df)} rows into TimescaleDB table '{TABLE_NAME}'")
    except Exception as e:
        print(f"Error inserting data into TimescaleDB: {e}")

if __name__ == "__main__":
    main()
