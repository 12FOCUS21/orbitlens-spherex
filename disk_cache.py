"""Limpieza del disco solo cuando no hay constructores activos."""
import re
import shutil
import time
from pathlib import Path

RESULT = re.compile(r"[a-f0-9]{24}(?:-[a-f0-9]{8})?")


def footprint(root):
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file() and not p.is_symlink()) if root.exists() else 0


def trim(raw, cache, protected, budget, now=None):
    """Presupuesto blando: retener una hora los archivos usados recientemente."""
    now = time.time() if now is None else now
    raw, cache = Path(raw).resolve(), Path(cache).resolve()
    total = footprint(raw) + footprint(cache)
    candidates = []
    for root, pattern in ((cache, "*"), (raw / "queries", "*"), (raw / "cutouts", "*.fits")):
        if not root.exists():
            continue
        for path in root.glob(pattern):
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                continue
            if root == cache and (not path.is_dir() or not RESULT.fullmatch(path.name) or path.name in protected):
                continue
            if root == raw / "queries" and not RESULT.fullmatch(path.name):
                continue
            stamp = path.stat().st_mtime
            if now - stamp >= 3600:
                candidates.append((stamp, path))
    removed = []
    for _, path in sorted(candidates):
        if total <= budget:
            break
        size = footprint(path) if path.is_dir() else path.stat().st_size
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        total -= size
        if path.parent == cache:
            removed.append(path.name)
    return removed, total
