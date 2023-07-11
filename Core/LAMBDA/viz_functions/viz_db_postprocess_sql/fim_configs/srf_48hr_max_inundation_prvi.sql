--Add an empty row so that service monitor will pick up a reference and update time in the event of no fim features
INSERT INTO ingest.srf_48hr_max_inundation_prvi(
	hydro_id, hydro_id_str, geom, branch, feature_id, feature_id_str, streamflow_cfs, hand_stage_ft, max_rc_stage_ft, max_rc_discharge_cfs, fim_version, reference_time, huc8)
	VALUES (-9999, '-9999', NULL, 'NA', -9999, '-9999', -9999, -9999, -9999, -9999, 'NA', to_char('1900-01-01 00:00:00'::timestamp without time zone, 'YYYY-MM-DD HH24:MI:SS UTC'), '-9999');

DROP TABLE IF EXISTS publish.srf_48hr_max_inundation_prvi;

SELECT  
	inun.hydro_id,
	inun.hydro_id_str::TEXT AS hydro_id_str,
	inun.branch,
	inun.feature_id,
	inun.feature_id_str::TEXT AS feature_id_str,
	inun.streamflow_cfs,
	inun.hand_stage_ft,
	inun.max_rc_stage_ft,
	inun.max_rc_discharge_cfs,
	inun.fim_version,
	to_char('1900-01-01 00:00:00'::timestamp without time zone, 'YYYY-MM-DD HH24:MI:SS UTC') AS reference_time,
	inun.huc8,
	inun.geom,
	to_char(now()::timestamp without time zone, 'YYYY-MM-DD HH24:MI:SS UTC') AS update_time, 
	channels.strm_order, 
    channels.name,
	'PRVI' AS state
INTO publish.srf_48hr_max_inundation_prvi
FROM ingest.srf_48hr_max_inundation_prvi as inun 
left join derived.channels_conus as channels ON channels.feature_id = inun.feature_id
--Add an empty row so that service monitor will pick up a reference and update time in the event of no fim features.
UNION SELECT -9999, '-9999', 'NA', -9999, '-9999', -9999, -9999, -9999, -9999, 'NA', to_char('1900-01-01 00:00:00'::timestamp without time zone, 'YYYY-MM-DD HH24:MI:SS UTC'),
'-9999', NULL, to_char(now()::timestamp without time zone, 'YYYY-MM-DD HH24:MI:SS UTC') AS update_time, -9999, NULL, 'PRVI';