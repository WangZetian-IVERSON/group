"""
tripo_finalize_watcher.py

Watch `tools/tripo_output` for newly created .glb/.gltf files. When a new file
appears and becomes stable (no size changes for `stable_seconds`) the watcher
writes `http://127.0.0.1:8000/<filename>` into `tools/last_model_url.txt` and
logs events to `tools/tripo_finalize_watcher.log`.

Usage:
    python tools/tripo_finalize_watcher.py

Run it as a background process or a service. It uses simple polling and no
external dependencies.
"""

import time
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
OUT_DIR = BASE / 'tools' / 'tripo_output'
LAST_URL = BASE / 'tools' / 'last_model_url.txt'
LOG = BASE / 'tools' / 'tripo_finalize_watcher.log'

# How long a file must be unchanged to be considered "stable" (seconds)
STABLE_SECONDS = 5
# How often to poll the directory (seconds)
POLL_INTERVAL = 1


def log(msg: str):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open('a', encoding='utf-8') as f:
            f.write(f'[{ts}] {msg}\n')
    except Exception:
        pass


def get_models():
    if not OUT_DIR.exists():
        return []
    return [p for p in OUT_DIR.iterdir() if p.suffix.lower() in ('.glb', '.gltf') and p.is_file()]


def newest_model():
    ms = get_models()
    if not ms:
        return None
    return max(ms, key=lambda p: p.stat().st_mtime)


def is_stable(path: Path, stable_seconds: int) -> bool:
    """Return True if file's size hasn't changed for `stable_seconds` seconds."""
    try:
        last_size = path.stat().st_size
    except Exception:
        return False
    # wait up to stable_seconds checking size
    waited = 0
    while waited < stable_seconds:
        time.sleep(1)
        waited += 1
        try:
            size = path.stat().st_size
        except Exception:
            return False
        if size != last_size:
            # changed — not stable
            return False
    return True


def update_last_url(newest: Path):
    try:
        url = f'http://127.0.0.1:8000/{newest.name}'
        LAST_URL.write_text(url, encoding='utf-8')
        log(f'Updated last_model_url to {url}')
    except Exception as e:
        log(f'Failed to update last_model_url: {e}')


def main():
    log('tripo_finalize_watcher starting')
    last_written = None
    try:
        # initialize last_written from existing last_model_url.txt if present
        if LAST_URL.exists():
            try:
                last_written = Path(LAST_URL.read_text(encoding='utf-8').strip()).name
            except Exception:
                last_written = None

        while True:
            try:
                new = newest_model()
                if new is None:
                    time.sleep(POLL_INTERVAL)
                    continue
                # if we already wrote this name, skip
                if new.name == last_written:
                    time.sleep(POLL_INTERVAL)
                    continue

                # wait until file is stable (size not changing)
                # if not stable, skip and let next loop re-evaluate
                if not is_stable(new, STABLE_SECONDS):
                    # file still being written
                    time.sleep(POLL_INTERVAL)
                    continue

                # final check: ensure no other file became newer while we waited
                now_newest = newest_model()
                if now_newest is None:
                    time.sleep(POLL_INTERVAL)
                    continue
                if now_newest.name != new.name:
                    # another file is newer; loop will handle it next
                    time.sleep(POLL_INTERVAL)
                    continue

                # All good — update last_model_url.txt and record
                update_last_url(new)
                last_written = new.name

            except Exception as e:
                log(f'Watcher loop error: {e}')
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        log('tripo_finalize_watcher stopped by KeyboardInterrupt')
    except Exception as e:
        log(f'Watcher terminated: {e}')


if __name__ == '__main__':
    main()
