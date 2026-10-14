"""Controller-only, process-lifetime temporary image storage."""
import base64
from pathlib import Path
import tempfile
import threading
import time
import uuid

MAX_IMAGE = 32 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_FILES = 100
MAX_AGE = 3600
_lock = threading.RLock()
_folder = None

def folder():
    global _folder
    with _lock:
        if _folder is None:
            import config
            temp_root=config.DATA_DIR/'tmp'
            temp_root.mkdir(parents=True,exist_ok=True)
            _folder = tempfile.TemporaryDirectory(prefix='captures-',dir=temp_root)
        return Path(_folder.name)

def _cleanup(incoming):
    entries = sorted(folder().iterdir(), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in entries)
    count = len(entries)
    cutoff = time.time() - MAX_AGE
    for p in entries:
        stat = p.stat()
        if stat.st_mtime < cutoff or count >= MAX_FILES or total + incoming > MAX_TOTAL:
            p.unlink()
            count -= 1
            total -= stat.st_size

def save(raw, content_type, capture_id=None):
    if len(raw) > MAX_IMAGE:
        raise ValueError('이미지가 너무 큽니다. 작은 영역을 캡처해 주세요.')
    mime = content_type.split(';')[0].strip().lower()
    if not mime.startswith('image/'):
        raise ValueError('이미지 응답이 필요합니다.')
    suffix = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}.get(mime, '.img')
    with _lock:
        _cleanup(len(raw))
        ident = capture_id or uuid.uuid4().hex
        if not isinstance(ident,str) or len(ident)!=32 or any(c not in '0123456789abcdef' for c in ident):
            raise ValueError('Invalid capture ID')
        path = folder() / (ident + suffix)
        try:
            with path.open('xb') as stream:
                stream.write(raw)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return dict(encoding='local_file', local_path=str(path), capture_id=ident,
                    storage='controller_temp', temporary=True, content_type=mime, bytes=len(raw))

def read(result):
    with _lock:
        path = Path(result['local_path'])
        if path.is_symlink() or path.resolve().parent != folder().resolve():
            raise ValueError('제어 PC 캡처 임시 폴더의 파일만 읽을 수 있습니다.')
        if path.stem != result.get('capture_id') or len(path.stem) != 32 or any(c not in '0123456789abcdef' for c in path.stem):
            raise ValueError('캡처 파일 ID가 올바르지 않습니다.')
        if path.stat().st_size > MAX_IMAGE:
            raise ValueError('이미지가 너무 큽니다.')
        return path.read_bytes()

def lookup(screenshot_id):
    """Resolve a controller capture ID without accepting arbitrary file paths."""
    if not isinstance(screenshot_id, str) or len(screenshot_id) != 32 or any(c not in '0123456789abcdef' for c in screenshot_id):
        raise ValueError('캡처 파일 ID가 올바르지 않습니다.')
    with _lock:
        for suffix, mime in (('.png', 'image/png'), ('.jpg', 'image/jpeg'), ('.webp', 'image/webp'), ('.img', 'image/unknown')):
            path = folder() / (screenshot_id + suffix)
            if path.is_file():
                result = dict(encoding='local_file', local_path=str(path), capture_id=screenshot_id,
                              storage='controller_temp', temporary=True, content_type=mime)
                result['bytes'] = len(read(result))
                return result
    raise ValueError('캡처를 찾을 수 없습니다. 만료되었거나 서버가 재시작되었습니다. 다시 캡처해 주세요.')

def image_bytes(result):
    if result.get('encoding') == 'local_file':
        return read(result)
    # Compatibility for callers supplying an in-memory response: save first, then read.
    raw = base64.b64decode(result['data'], validate=True)
    stored = save(raw, result['content_type'])
    result.pop('data', None)
    result.update(stored)
    return read(result)
