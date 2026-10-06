from __future__ import annotations
from io import BytesIO
from pathlib import Path
from typing import Mapping
import pandas as pd
import requests


def fetch_file(
    url: str,
    destination: str | Path,
    *,
    params: Mapping | None = None,
    headers: Mapping | None = None,
    timeout: int = 60,
) -> Path:
    """
    Generic HTTP downloader for public-data endpoints.

    API-specific authentication, pagination and parameter rules should be supplied
    by the Agent/orchestrator or a source-specific adapter. Analysis code must not
    contain API keys.
    """
    response = requests.get(url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return path


def read_table(path: str | Path, **kwargs) -> pd.DataFrame:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, **kwargs)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, **kwargs)
    if suffix == ".parquet":
        return pd.read_parquet(path, **kwargs)
    raise ValueError(f"Unsupported table format: {suffix}")
