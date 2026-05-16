-- ============================================================
-- kpi_hourly_engine_agg.sql
-- Creates a materialized view of hourly telemetry metrics
-- Idempotent: Drops existing view before creating
-- ============================================================

DROP MATERIALIZED VIEW IF EXISTS kpi_hourly_telemetry;

CREATE MATERIALIZED VIEW IF NOT EXISTS kpi_hourly_telemetry AS
SELECT
	asset_id,
	time_bucket('1 hour', timestamp) AS bucket,
	ROUND(AVG(engine_rpm)::numeric, 0) AS avg_rpm,
	MIN(engine_rpm) AS min_rpm,
	MAX(engine_rpm) AS max_rpm,
	ROUND(AVG(engine_load_pct)::numeric, 1) AS avg_engine_load_pct,
	ROUND(AVG(coolant_temp_c)::numeric, 1) AS avg_coolant_temp_c,
	ROUND(MAX(coolant_temp_c)::numeric, 1)   AS max_coolant_temp_c,
	ROUND(AVG(oil_temp_c)::numeric, 1)       AS avg_oil_temp_c,
	ROUND(MAX(oil_temp_c)::numeric, 1)       AS max_oil_temp_c,
	ROUND(AVG(turbo_boost_kpa)::numeric, 1)  AS avg_turbo_boost_kpa,
	ROUND(MAX(turbo_boost_kpa)::numeric, 1)  AS max_turbo_boost_kpa,
	ROUND(AVG(hydraulic_pressure_kpa)::numeric, 0) AS avg_hydraulic_pressure_kpa,
	MAX(hydraulic_pressure_kpa) AS max_hydraulic_pressure_kpa,
	-- liters consumed approximation: fuel_rate_lph sampled every 5s -> litres = sum(fuel_rate_lph * 5sec / 3600)
  	ROUND( (SUM(fuel_rate_lph) * (5.0/3600.0))::numeric, 1) AS liters_consumed_est,
	-- (5 sec/samples) / (60 seconds/min) = 0.0833 ratio
  	ROUND( SUM((duty_cycle_stage = 'IDLE')::int) * 0.0833::numeric, 1)  AS idle_mins,  
  	ROUND( SUM((duty_cycle_stage = 'LOAD')::int) * 0.0833::numeric, 1)  AS load_mins,
	ROUND( SUM((duty_cycle_stage = 'HAUL')::int) * 0.0833::numeric, 1)  AS haul_mins,
  	ROUND( SUM((duty_cycle_stage = 'DUMP')::int) * 0.0833::numeric, 1)  AS dump_mins,
	ROUND( SUM((duty_cycle_stage = 'RETURN')::int) * 0.0833::numeric, 1)  AS return_mins,
	COUNT(DISTINCT cycle_number) AS cycles_count
FROM engine_telemetry
GROUP BY asset_id, bucket
ORDER BY asset_id ASC, bucket ASC;

SELECT * FROM kpi_hourly_telemetry LIMIT 10;
