"""Temporary workspace with inherited Windows ACLs (no owner-only mkdir)."""
from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile
import uuid


@contextmanager
def temporary_directory(parent=None):
    root = Path(parent or tempfile.gettempdir()).resolve()
    path = root / ('analysis2_' + uuid.uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        # Only the exact newly-created child is removed; never an input directory.
        if path.parent != root or not path.name.startswith('analysis2_'):
            raise RuntimeError('Unsafe temporary cleanup path')
        shutil.rmtree(path)
