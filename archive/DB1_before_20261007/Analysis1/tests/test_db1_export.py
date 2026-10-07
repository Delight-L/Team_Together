import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT.parent / "outputs" / "db1.sqlite"

def test_analysis1_db1_baseline():
    assert DB.exists()
    with sqlite3.connect(DB) as con:
        assert con.execute("SELECT COUNT(*) FROM a1_region_baseline").fetchone()[0] == 22
        assert con.execute("SELECT COUNT(*) FROM a1_region_feature WHERE period='2025H2'").fetchone()[0] == 286
        dist = dict(con.execute("SELECT cluster_id, COUNT(*) FROM a1_region_baseline GROUP BY cluster_id").fetchall())
        assert dist == {0: 7, 1: 3, 2: 12}
        assert con.execute("SELECT COUNT(*) FROM (SELECT adm_cd, baseline_period, COUNT(*) n FROM a1_region_baseline GROUP BY 1,2 HAVING n>1)").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM (SELECT adm_cd, period, feature_name, COUNT(*) n FROM a1_region_feature GROUP BY 1,2,3 HAVING n>1)").fetchone()[0] == 0
