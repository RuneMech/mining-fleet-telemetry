-- ============================================================
-- kpi_hourly_combined.sql
-- Materialized Hourly KPI Table (Telemetry + Faults)
-- ============================================================

DROP MATERIALIZED VIEW IF EXISTS kpi_hourly_combined;

CREATE MATERIALIZED VIEW kpi_hourly_combined AS
SELECT
    t.asset_id,
    t.bucket,

    -- telemetry KPIs
    t.avg_rpm,
    t.min_rpm,
    t.max_rpm,
    t.avg_engine_load_pct,
    t.avg_coolant_temp_c,
    t.max_coolant_temp_c,
    t.avg_oil_temp_c,
    t.max_oil_temp_c,
    t.avg_turbo_boost_kpa,
    t.max_turbo_boost_kpa,
    t.avg_hydraulic_pressure_kpa,
    t.max_hydraulic_pressure_kpa,
    t.liters_consumed_est,
    t.idle_mins,
    t.load_mins,
    t.haul_mins,
    t.dump_mins,
    t.return_mins,
    t.cycles_count,

    -- fault KPIs
    (COALESCE(f.fault_event_count, 0) > 0) AS has_faults,
    COALESCE(f.fault_event_count, 0)      AS fault_event_count,
    COALESCE(f.faults_engine_rpm, 0)      AS faults_engine_rpm,
    COALESCE(f.faults_coolant_temp, 0)    AS faults_coolant_temp,
    COALESCE(f.faults_oil_temp, 0)        AS faults_oil_temp,
    COALESCE(f.faults_fuel_rate, 0)       AS faults_fuel_rate,
    COALESCE(f.faults_hydraulic, 0)       AS faults_hydraulic,
    COALESCE(f.faults_turbo, 0)           AS faults_turbo

FROM kpi_hourly_telemetry t
LEFT JOIN kpi_hourly_faults f ON t.asset_id = f.asset_id AND t.bucket   = f.bucket

ORDER BY t.asset_id, t.bucket;
