import pandas as pd, numpy as np

def compare_to_reference(actual, reference, atol=1e-10):
    a=actual.sort_values('dong_name').reset_index(drop=True); r=reference.sort_values('dong_name').reset_index(drop=True)
    common=[c for c in r.columns if c in a.columns]
    rows=[]
    for c in common:
        if c in ('dong_name','adm_cd'):
            ok=a[c].astype(str).equals(r[c].astype(str)); diff=None
        else:
            av=pd.to_numeric(a[c],errors='coerce'); rv=pd.to_numeric(r[c],errors='coerce')
            diff=float(np.nanmax(np.abs(av-rv))) if len(av) else 0.; ok=bool(np.allclose(av,rv,atol=atol,equal_nan=True))
        rows.append({'column':c,'match':ok,'max_abs_diff':diff})
    return pd.DataFrame(rows)
