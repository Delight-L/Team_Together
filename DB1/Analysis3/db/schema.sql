CREATE TABLE IF NOT EXISTS a3_run (
 source TEXT NOT NULL,period TEXT NOT NULL,fingerprint TEXT NOT NULL,
 version TEXT NOT NULL,available_from TEXT,metadata_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(source,period));
CREATE TABLE IF NOT EXISTS a3_policy (id INTEGER PRIMARY KEY CHECK(id=1),policy_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS a3_dimension (age TEXT NOT NULL,domain TEXT NOT NULL,PRIMARY KEY(age,domain));
CREATE TABLE IF NOT EXISTS a3a_industry (
 period TEXT NOT NULL,adm_cd TEXT NOT NULL,industry TEXT NOT NULL,domain TEXT,
 payload_json TEXT NOT NULL,PRIMARY KEY(period,adm_cd,industry));
CREATE TABLE IF NOT EXISTS a3b_industry (
 period TEXT NOT NULL,district TEXT NOT NULL,age_raw TEXT NOT NULL,age TEXT NOT NULL,
 industry TEXT NOT NULL,domain TEXT,payload_json TEXT NOT NULL,
 PRIMARY KEY(period,district,age_raw,industry));
CREATE TABLE IF NOT EXISTS a3a_feature (
 period TEXT NOT NULL,adm_cd TEXT NOT NULL,age TEXT NOT NULL,domain TEXT NOT NULL,
 observed_industries INTEGER NOT NULL,payload_json TEXT NOT NULL,
 PRIMARY KEY(period,adm_cd,age,domain));
CREATE TABLE IF NOT EXISTS a3a_comparison (
 period TEXT NOT NULL,adm_cd TEXT NOT NULL,age TEXT NOT NULL,domain TEXT NOT NULL,
 baseline_n INTEGER NOT NULL,comparison_available INTEGER NOT NULL,
 payload_json TEXT NOT NULL,PRIMARY KEY(period,adm_cd,age,domain));
CREATE TABLE IF NOT EXISTS a3b_feature (
 period TEXT NOT NULL,district TEXT NOT NULL,age TEXT NOT NULL,domain TEXT NOT NULL,
 observed_industries INTEGER NOT NULL,payload_json TEXT NOT NULL,
 PRIMARY KEY(period,district,age,domain));
CREATE TABLE IF NOT EXISTS a3b_total (
 period TEXT NOT NULL,district TEXT NOT NULL,age TEXT NOT NULL,payload_json TEXT NOT NULL,
 PRIMARY KEY(period,district,age));
CREATE TABLE IF NOT EXISTS a3a_quarter_summary (
 period TEXT NOT NULL,adm_cd TEXT NOT NULL,payload_json TEXT NOT NULL,
 PRIMARY KEY(period,adm_cd));
CREATE TABLE IF NOT EXISTS a3b_month_summary (
 period TEXT NOT NULL,district TEXT NOT NULL,payload_json TEXT NOT NULL,
 PRIMARY KEY(period,district));
CREATE VIEW IF NOT EXISTS v_a123_monthly AS
 SELECT i.*,substr(i.date,1,4)||'Q'||CAST(((CAST(substr(i.date,6,2) AS INTEGER)-1)/3+1) AS INTEGER) AS a3a_period,
 'retrospective_same_quarter' AS a3a_alignment,
 'merchant_dong' AS a3a_scope,'merchant_district_context' AS a3b_scope,
 a.payload_json AS a3a_summary,b.payload_json AS a3b_summary,
 ra.available_from AS a3a_available_from,rb.available_from AS a3b_available_from
 FROM v_db1_integrated i
 LEFT JOIN a3a_quarter_summary a ON a.adm_cd=i.adm_cd AND a.period=substr(i.date,1,4)||'Q'||CAST(((CAST(substr(i.date,6,2) AS INTEGER)-1)/3+1) AS INTEGER)
 LEFT JOIN a3b_month_summary b ON b.period=substr(i.date,1,7) AND b.district='11680'
 LEFT JOIN a3_run ra ON ra.source='market' AND ra.period=a.period
 LEFT JOIN a3_run rb ON rb.source='card' AND rb.period=b.period;
DROP VIEW IF EXISTS v_a123_detail;
CREATE VIEW v_a123_detail AS
 SELECT i.date,i.adm_cd,i.adm_nm,i.a1_cluster,i.a1_cluster_type,i.context_period,
 i.any_signal,i.communication_signal,i.mobility_signal,i.combined_signal,i.signal_status,
 dims.age,dims.domain,substr(i.date,1,4)||'Q'||CAST(((CAST(substr(i.date,6,2) AS INTEGER)-1)/3+1) AS INTEGER) AS a3a_period,f.payload_json AS a3a_feature,
 c.payload_json AS a3a_comparison,b.payload_json AS a3b_month_context,
 'retrospective_same_quarter' AS a3a_alignment,'merchant_district_context' AS a3b_scope
 FROM v_db1_integrated i
 CROSS JOIN a3_dimension dims
 LEFT JOIN a3a_feature f ON f.adm_cd=i.adm_cd AND f.age=dims.age AND f.domain=dims.domain AND f.period=substr(i.date,1,4)||'Q'||CAST(((CAST(substr(i.date,6,2) AS INTEGER)-1)/3+1) AS INTEGER)
 LEFT JOIN a3a_comparison c ON c.period=f.period AND c.adm_cd=f.adm_cd AND c.age=f.age AND c.domain=f.domain
 LEFT JOIN a3b_feature b ON b.period=substr(i.date,1,7) AND b.age=dims.age AND b.domain=dims.domain AND b.district='11680';
CREATE VIEW IF NOT EXISTS v_a123_available_context AS
 SELECT i.date,i.adm_cd,i.adm_nm,i.context_period,i.a1_cluster_type,i.any_signal,
 a.period AS a3a_period,a.payload_json AS a3a_summary,
 b.period AS a3b_period,b.payload_json AS a3b_summary,
 'publication_date_checked' AS alignment
 FROM v_db1_integrated i
 LEFT JOIN a3a_quarter_summary a ON a.adm_cd=i.adm_cd AND a.period=(
  SELECT MAX(s.period) FROM a3a_quarter_summary s JOIN a3_run r ON r.source='market' AND r.period=s.period
  WHERE s.adm_cd=i.adm_cd AND r.available_from IS NOT NULL
  AND r.available_from<=date(i.date,'start of month','+1 month','-1 day'))
 LEFT JOIN a3b_month_summary b ON b.district='11680' AND b.period=(
  SELECT MAX(s.period) FROM a3b_month_summary s JOIN a3_run r ON r.source='card' AND r.period=s.period
  WHERE s.district='11680' AND r.available_from IS NOT NULL
  AND r.available_from<=date(i.date,'start of month','+1 month','-1 day'));
CREATE VIEW IF NOT EXISTS v_a2_quarter AS
 SELECT adm_cd,substr(date,1,4)||'Q'||CAST(((CAST(substr(date,6,2) AS INTEGER)-1)/3+1) AS INTEGER) AS period,
 COUNT(*) AS observed_months,3 AS expected_months,SUM(any_signal) AS signal_months,
 SUM(communication_signal) AS communication_months,SUM(mobility_signal) AS mobility_months,
 SUM(combined_signal) AS combined_months,
 GROUP_CONCAT(CASE WHEN any_signal=1 THEN substr(date,1,7) END) AS signal_month_list
 FROM a2_detection GROUP BY adm_cd,period;
