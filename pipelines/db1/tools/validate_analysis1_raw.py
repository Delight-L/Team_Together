import sys as _settings_sys
from pathlib import Path as _SettingsPath

_settings_sys.path.insert(0, str(_SettingsPath(__file__).resolve().parents[1]))
from db1_settings import load_settings
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
c = load_settings(ROOT / 'config/db1_config.json')['analysis1']
args = [
    sys.executable,
    str(ROOT / 'Analysis1/run_full_preprocessing.py'),
    '--skt-source',
    c['skt_source'],
    '--boundary',
    c['boundary'],
    '--period',
    '2025H2',
    '--reference',
    str(ROOT / 'Analysis1/data/reference/reference_pca_input_2025H2.csv'),
    '--work-dir',
    str(ROOT / 'Analysis1/data/raw/skt'),
    '--out-dir',
    str(ROOT / 'Analysis1/data/processed/2025H2'),
]
for name, path in c['public'].items():
    args += ['--' + name, path]
subprocess.run(args, check=True)
