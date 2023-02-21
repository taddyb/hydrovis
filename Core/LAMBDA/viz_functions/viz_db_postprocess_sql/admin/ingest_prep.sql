--> Let the database know that ingest has started
INSERT INTO admin.ingest_status (target, reference_time, status, update_time)
VALUES ('{target_table}', '1900-01-01 00:00:00', 'Import Started', now()::timestamp without time zone);

--> Drop target table index (if exists)
DROP INDEX IF EXISTS {target_schema}.{index_name};

--> Truncate target table
TRUNCATE TABLE {target_table};