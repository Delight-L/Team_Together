from pathlib import Path
import openpyxl,json
R=Path(__file__).resolve().parent
DB1=next((p for p in R.parents if (p/'run_db1.py').exists()),Path(r'C:\Users\user\Desktop\Team_Together\DB1'))
p=DB1.parent/'서울시 공공데이터/서울 시민생활 데이터/서울시민생활데이터_컬럼설명서.xlsx'
w=openpyxl.load_workbook(p,read_only=True,data_only=True)
rows=[]
for s in w:
 for i,row in enumerate(s.iter_rows(values_only=True),1):
  values=[str(v) if v is not None else '' for v in row[:8]]
  if any(any(t in v for t in ['SNS','통화대상','문자대상','휴일','평일','개월','기간','카카오']) for v in values):rows.append({'sheet':s.title,'row':i,'values':values})
w.close()
out=DB1/'outputs/validation/retrospective_20261007' if (R/'DEPLOYED.txt').exists() else R/'outputs';out.mkdir(parents=True,exist_ok=True)
(out/'source_definitions.json').write_text(json.dumps({'path':str(p),'matching_rows':rows},ensure_ascii=False,indent=2),encoding='utf-8')
for r in rows:
 if r['values'][1] in ['SNS 사용횟수','카카오톡 비사용 인구수','평균 통화대상자 수','평균 문자대상자 수','평일 총 이동 횟수','휴일 총 이동 횟수 평균']:print(r)
