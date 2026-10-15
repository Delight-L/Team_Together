-- Preferred integration: label date and observation dates are explicit.
-- Legacy team views with same-label consumption remain for compatibility only.
CREATE VIEW IF NOT EXISTS v_v15_monthly_context AS
 SELECT i.*,w.payload_json AS observation_window_json,
 json_extract(w.payload_json,'$.observation_start') AS observation_start,
 json_extract(w.payload_json,'$.observation_end') AS observation_end,
 json_extract(w.payload_json,'$.exact_quarter') AS exact_observation_quarter,
 a.payload_json AS same_window_dong_consumption_json,
 (SELECT json_group_array(json_object('period',b.period,'context',json(b.payload_json)))
    FROM a3b_month_summary b WHERE b.district='11680'
    AND b.period>=substr(json_extract(w.payload_json,'$.observation_start'),1,7)
    AND b.period<=substr(json_extract(w.payload_json,'$.observation_end'),1,7)) AS district_shared_consumption_json,
 weather.payload_json AS observation_weather_json,
 'merchant_context_not_resident_consumption' AS consumption_scope,
 1 AS retrospective_only,0 AS live_availability_verified
 FROM v_db1_integrated i
 LEFT JOIN a2_observation_window w ON w.date=i.date
 LEFT JOIN a3a_quarter_summary a ON a.adm_cd=i.adm_cd AND a.period=json_extract(w.payload_json,'$.exact_quarter')
 LEFT JOIN ctx_weather weather ON weather.date=i.date;

CREATE VIEW IF NOT EXISTS v_v15_age_context AS
 SELECT d.*,weather.payload_json AS observation_weather_json,
 (SELECT json_group_array(json(s.payload_json)) FROM ctx_survey_annual s
   WHERE s.survey='seoul_survey' AND s.district='gangnam' AND s.age_band=d.age_band
   AND s.year=(SELECT MAX(x.year) FROM ctx_survey_annual x WHERE x.survey='seoul_survey'
               AND x.year<=CAST(substr(d.source_label_date,1,4) AS INTEGER))) AS district_annual_survey_json,
 CASE WHEN d.age_band='60plus' THEN (SELECT e.payload_json FROM ctx_elder_annual e
   WHERE e.adm_cd=d.adm_cd AND e.year<=CAST(substr(d.source_label_date,1,4) AS INTEGER)
   ORDER BY e.year DESC LIMIT 1) END AS partial_age_65plus_elder_json,
 l.payload_json AS activity_level_json,
 'district_not_dong' AS survey_scope,1 AS retrospective_only,0 AS live_availability_verified
 FROM v_a123_age_source_context d
 LEFT JOIN ctx_weather weather ON weather.date=d.source_label_date
 LEFT JOIN a2_activity_level l ON l.adm_cd=d.adm_cd AND l.date=d.source_label_date AND l.age_band=d.age_band;
