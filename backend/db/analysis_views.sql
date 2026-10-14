-- 조회 정의만 등록합니다. 기존 분석 테이블과 데이터는 변경하지 않습니다.
CREATE VIEW db1.latest_detection_run AS
SELECT run_id FROM db1.analysis2_detections
GROUP BY run_id ORDER BY MAX(created_at) DESC LIMIT 1;

CREATE VIEW db1.latest_region_typology AS
SELECT adm_cd, dong_name, cluster_type, payload, source_file
FROM (
    SELECT adm_cd, dong_name, cluster_type, payload, source_file,
           ROW_NUMBER() OVER (PARTITION BY adm_cd ORDER BY created_at DESC) AS position
    FROM db1.analysis1_region_typology
) latest WHERE position = 1;
