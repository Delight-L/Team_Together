import hashlib
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from .readers import month_from_name


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def restored_name(info):
    name = info.filename
    if not info.flag_bits & 0x800:
        try:
            name = name.encode('cp437').decode('cp949')
        except (UnicodeError, LookupError):
            pass
    return name


def safe_name(name):
    p = PurePosixPath(name.replace('\\', '/'))
    if p.is_absolute() or '..' in p.parts or any(':' in x for x in p.parts):
        raise ValueError(f'안전하지 않은 ZIP 경로: {name}')
    return p


def discover(inputs, scratch, limits, manifest):
    """Stream ZIP members to numbered scratch paths; never trust member paths."""
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    seen, result = {}, []
    total, count = 0, 0

    def visit(path, source, name, depth):
        nonlocal total, count
        digest = sha256(path)
        entry = dict(source=source, name=name, sha256=digest, bytes=path.stat().st_size)
        manifest['files'].append(entry)
        suffix = Path(name).suffix.lower()
        identity = (suffix, month_from_name(name), digest) if suffix == '.xlsx' else (suffix, digest)
        if suffix in {'.zip', '.xlsx'} and identity in seen:
            entry.update(status='duplicate', duplicate_of=seen[identity])
            return
        if suffix in {'.zip', '.xlsx'}:
            seen[identity] = source
        if suffix == '.xlsx':
            entry['status'] = 'discovered'
            result.append((path, name, entry))
        elif suffix == '.zip':
            if depth >= limits['max_depth']:
                raise ValueError(f'ZIP 깊이 제한 초과: {source}')
            entry['status'] = 'archive'
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    decoded = restored_name(info)
                    safe_name(decoded)
                    if stat.S_ISLNK(info.external_attr >> 16):
                        raise ValueError(f'ZIP 심볼릭 링크 금지: {source}!{decoded}')
                    if info.is_dir():
                        continue
                    count += 1
                    if count > limits['max_files'] or info.file_size > limits['max_file_bytes']:
                        raise ValueError('ZIP 파일 개수 또는 개별 크기 제한 초과')
                    if total + info.file_size > limits['max_total_bytes']:
                        raise ValueError('ZIP 전체 해제 크기 제한 초과')
                    target = scratch / f'{count:06d}{Path(decoded).suffix.lower()}'
                    written = 0
                    with archive.open(info) as src, target.open('wb') as dst:
                        while block := src.read(1024 * 1024):
                            written += len(block)
                            total += len(block)
                            if written > limits['max_file_bytes'] or total > limits['max_total_bytes']:
                                raise ValueError('ZIP 실제 해제 크기 제한 초과')
                            dst.write(block)
                    visit(target, source + '!' + decoded, decoded, depth + 1)
        else:
            entry['status'] = 'excluded_unsupported_extension'

    for input_path in inputs:
        if Path(input_path).is_symlink():
            raise ValueError(f'입력 심볼릭 링크 금지: {input_path}')
        root = Path(input_path).resolve()
        if not root.exists():
            raise ValueError(f'입력 경로 없음: {root}')
        paths = sorted(root.rglob('*')) if root.is_dir() else [root]
        for p in paths:
            if p.is_symlink():
                raise ValueError(f'입력 심볼릭 링크 금지: {p}')
            if p.is_file():
                if p.suffix.lower() in {'.zip', '.xlsx'}:
                    count += 1
                    if count > limits['max_files'] or p.stat().st_size > limits['max_file_bytes']:
                        raise ValueError('입력 파일 개수 또는 개별 크기 제한 초과')
                visit(p, str(p), p.name, 0)
    manifest['extracted_bytes'] = total
    return result
