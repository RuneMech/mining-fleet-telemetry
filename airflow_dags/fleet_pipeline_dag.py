from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from datetime import datetime

# -------------------------------------------------------------------
# DAG definition
# -------------------------------------------------------------------
with DAG(
    dag_id="fleet_telemetry_pipeline",
    description="Hourly fleet telemetry KPI pipeline (manual demo)",
    start_date=datetime(2025, 12, 30),
    schedule_interval=None,   # manual runs only
    catchup=False,
    template_searchpath=["/opt/airflow/scripts/sql"],
    tags=["telemetry", "timescaledb", "portfolio"],
) as dag:

    # -------------------------------------------------------------------
    # 1. Generate engine telemetry data
    # -------------------------------------------------------------------
    generate_telemetry = BashOperator(
        task_id="generate_engine_telemetry",
        bash_command="""
        python /opt/airflow/scripts/telemetry_df_generate.py
        """
    )

    # -------------------------------------------------------------------
    # 2. Detect faults from telemetry
    # -------------------------------------------------------------------
    detect_faults = BashOperator(
        task_id="detect_faults",
        bash_command="python /opt/airflow/scripts/fault_detector.py"
    )

    # -------------------------------------------------------------------
    # 3. Hourly telemetry KPIs
    # -------------------------------------------------------------------
    kpi_hourly_telemetry = PostgresOperator(
        task_id="kpi_hourly_telemetry",
        sql="kpi_hourly_engine_agg.sql",
        postgres_conn_id='timescaledb_postgres',  # connection created in Airflow,
        autocommit=True,
    )

    # -------------------------------------------------------------------
    # 4. Hourly fault KPIs
    # -------------------------------------------------------------------
    kpi_hourly_faults = PostgresOperator(
        task_id="kpi_hourly_faults",
        sql="kpi_hourly_faults_agg.sql",
        postgres_conn_id='timescaledb_postgres',
        autocommit=True,
    )

    # -------------------------------------------------------------------
    # 5. Combined KPI layer
    # -------------------------------------------------------------------
    kpi_hourly_combined = PostgresOperator(
        task_id="kpi_hourly_combined",
        sql="kpi_hourly_combined.sql",
        postgres_conn_id='timescaledb_postgres',
        autocommit=True,
    )

    # -------------------------------------------------------------------
    # Task dependencies
    # -------------------------------------------------------------------

    generate_telemetry >> detect_faults
    detect_faults >> [kpi_hourly_telemetry, kpi_hourly_faults]
    [kpi_hourly_telemetry, kpi_hourly_faults] >> kpi_hourly_combined

