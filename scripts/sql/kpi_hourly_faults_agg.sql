-- ============================================================
-- kpi_hourly_faults_agg.sql
-- Hourly fault counts per asset and subsystem
-- ============================================================

DROP MATERIALIZED VIEW IF EXISTS kpi_hourly_faults;

CREATE MATERIALIZED VIEW IF NOT EXISTS kpi_hourly_faults AS
SELECT
  asset_id,
  time_bucket('1 hour', timestamp_start) AS bucket,
  COUNT(*) AS fault_event_count,
  COUNT(*) FILTER (WHERE subsystem = 'engine_rpm')        AS faults_engine_rpm,
  COUNT(*) FILTER (WHERE subsystem = 'coolant_temp_c')    AS faults_coolant_temp,
  COUNT(*) FILTER (WHERE subsystem = 'oil_temp_c')        AS faults_oil_temp,
  COUNT(*) FILTER (WHERE subsystem = 'fuel_rate_lph')     AS faults_fuel_rate,
  COUNT(*) FILTER (WHERE subsystem = 'hydraulic_pressure_kpa') AS faults_hydraulic,
  COUNT(*) FILTER (WHERE subsystem = 'turbo_boost_kpa')   AS faults_turbo
FROM fault_events
GROUP BY asset_id, bucket
ORDER BY asset_id, bucket;
