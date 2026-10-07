import re
import pandas as pd

def halfyear(value):
    match=re.fullmatch(r'(20\d{2})H([12])',value)
    if not match: raise ValueError('period must be YYYYH1 or YYYYH2')
    year,half=int(match[1]),int(match[2])
    return year,(1,2) if half==1 else (3,4),pd.date_range(pd.Timestamp(year,1 if half==1 else 7,1),periods=6,freq='MS')

def quarter_indices(columns,year,quarters,width,offset,overrides=None):
    blocks=[]
    for quarter in quarters:
        label=f'{year}Q{quarter}'
        if overrides and label in overrides:
            indices=list(overrides[label])
        else:
            pattern=re.compile(rf'^{year}\s+{quarter}/4(?:\.\d+)?$')
            indices=[i for i,c in enumerate(columns) if pattern.match(str(c).strip())]
            if not indices and year==2025 and quarter==4 and width==11:
                indices=[i for i,c in enumerate(columns) if re.fullmatch(r'2025\s*(?:\.\d+)?',str(c).strip())]
        if len(indices)!=width or any(i<offset for i in indices):
            raise ValueError(f'Missing/ambiguous {label}: expected {width} columns, got {len(indices)}. Set quarter_blocks for nonstandard exports.')
        blocks.append((label,indices))
    return blocks
