"""Resolve portable DB1 source paths while preserving custom local settings."""
from pathlib import Path
import json
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / '.env')


def load_settings(path):
    data_root = Path(os.environ.get('TEAM_TOGETHER_DATA_ROOT') or ROOT.parent).resolve()
    def expand(value):
        if isinstance(value, dict):
            return {key: expand(item) for key, item in value.items()}
        if isinstance(value, list):
            return [expand(item) for item in value]
        if isinstance(value, str):
            return value.replace('${TEAM_TOGETHER_DATA_ROOT}', str(data_root))
        return value
    return expand(json.loads(Path(path).read_text(encoding='utf-8')))
