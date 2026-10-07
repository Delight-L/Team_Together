from pathlib import Path
import pandas as pd

ENCODINGS=("utf-8-sig","cp949","euc-kr","utf-8")

def read_local(path, *, sep=None, **kwargs):
    path=Path(path)
    if path.suffix.lower() in {".xlsx",".xls"}:
        return pd.read_excel(path, **kwargs)
    seps=[sep] if sep else [",","\t"]
    last=None
    for enc in ENCODINGS:
        for s in seps:
            try:
                df=pd.read_csv(path,encoding=enc,sep=s,low_memory=False,**kwargs)
                if sep is not None or df.shape[1] > 1:
                    return df
            except Exception as e: last=e
    raise ValueError(f"파일을 읽을 수 없습니다: {path} / {last}")
