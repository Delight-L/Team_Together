from pathlib import Path
from zipfile import ZipFile
import re

PREFIXES=('flow_age_pop','flow_time_pop','flow_wkdy_pop')

def prepare_skt_raw(source_dir: str|Path, target_dir: str|Path) -> dict[str,dict[str,Path]]:
    """Copy/extract SKT CSVs from a local folder and return prefix->month->path.
    ZIP filenames do not matter; member filenames determine data type/month.
    """
    src=Path(source_dir); dst=Path(target_dir); dst.mkdir(parents=True,exist_ok=True)
    for p in src.glob('*.csv'):
        if any(p.name.startswith(x+'_') for x in PREFIXES):
            out=dst/p.name
            if p.resolve()!=out.resolve(): out.write_bytes(p.read_bytes())
    for z in src.glob('*.zip'):
        with ZipFile(z) as f:
            for n in f.namelist():
                name=Path(n).name
                if name.lower().endswith('.csv') and any(name.startswith(x+'_') for x in PREFIXES):
                    with f.open(n) as r, open(dst/name,'wb') as w: w.write(r.read())
    found={x:{} for x in PREFIXES}
    for p in dst.glob('*.csv'):
        m=re.search(r'(20\d{4})',p.name)
        for prefix in PREFIXES:
            if p.name.startswith(prefix+'_') and m: found[prefix][m.group(1)]=p
    return found

def validate_month_coverage(found, months):
    missing=[]
    for prefix in PREFIXES:
        for month in months:
            if month not in found.get(prefix,{}): missing.append(f'{prefix}_{month}')
    if missing: raise FileNotFoundError('Missing SKT source files: '+', '.join(missing))
