SELECT table_schema || '.' || table_name || '=' ||
       (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I.%I', table_schema, table_name), false, true, '')))[1]::text
FROM information_schema.tables
WHERE table_schema IN ('db1', 'db2') AND table_type = 'BASE TABLE'
ORDER BY 1;
