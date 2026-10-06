import numpy as np
import pandas as pd
from data.validation import REQUIRED_COLUMNS,NUMERIC_COLUMNS
from common.config import DETECTION_CORE_COLUMNS,MOBILITY_EVIDENCE_COLUMNS,QC_COLUMNS,INTEREST_VALIDATION_COLUMNS


def validate_feature_rows(df, expected_codes=None):
    missing=set(REQUIRED_COLUMNS)-set(df)
    if missing: raise ValueError(f'Missing feature columns: {sorted(missing)}')
    dates=pd.to_datetime(df.date,format='mixed',errors='raise')
    if dates.isna().any() or not dates.eq(dates.dt.to_period('M').dt.to_timestamp()).all():
        raise ValueError('date must be the first day of each month')
    if df[REQUIRED_COLUMNS].isna().any().any(): raise ValueError('Missing required feature values')
    values=df[NUMERIC_COLUMNS].apply(pd.to_numeric,errors='raise')
    if not np.isfinite(values.to_numpy(float)).all(): raise ValueError('Nonfinite feature values')
    if (values[DETECTION_CORE_COLUMNS+MOBILITY_EVIDENCE_COLUMNS]<=0).any().any(): raise ValueError('Log inputs must be positive')
    if ((values[QC_COLUMNS+INTEREST_VALIDATION_COLUMNS]<0)|(values[QC_COLUMNS+INTEREST_VALIDATION_COLUMNS]>1)).any().any(): raise ValueError('Ratios must be between zero and one')
    if not (values.days_in_month==values.weekday_days+values.weekend_days).all(): raise ValueError('Invalid calendar counts')
    if df.duplicated(['date','행정동코드']).any(): raise ValueError('Duplicate date/area key')
    for _,group in df.assign(date=dates).groupby('date'):
        if len(group)!=22 or group['행정동코드'].nunique()!=22: raise ValueError('Expected 22 dongs per month')
        if expected_codes is not None and set(group['행정동코드'].astype(str))!=set(map(str,expected_codes)):
            raise ValueError('Area code set differs from baseline')


def validate_history(df):
    validate_feature_rows(df)
    dates=pd.DatetimeIndex(pd.to_datetime(df.date).unique()).sort_values()
    expected=pd.date_range('2022-01-01',dates.max(),freq='MS')
    if not dates.equals(expected): raise ValueError('History has missing/out-of-order months')
    codes=df.loc[pd.to_datetime(df.date)==dates[0],'행정동코드'].astype(str)
    validate_feature_rows(df,codes)
