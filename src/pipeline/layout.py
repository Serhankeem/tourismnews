"""Explicit data ownership; unknown files and symlinks never enter a snapshot."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = '.data-manifest.json'
CONTROL = 'control.json'


class DataError(ValueError):
    pass


def read(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise DataError('invalid_or_missing_json:' + Path(path).name) from None


def configuration(root=ROOT):
    cfg = read(Path(root)/'pipeline.json')
    if any(not name.startswith('site/data/') for name in cfg['public_files']) or any(not name.startswith('collector_state/') for name in cfg['private_files']):
        raise DataError('data_ownership_prefix_invalid')
    for name in cfg['public_files'] + cfg['private_files']:
        p = Path(name)
        if p.is_absolute() or '..' in p.parts or p.suffix != '.json' or len(p.parts) != (3 if name.startswith('site/data/') else 2):
            raise DataError('unsafe_data_path')
    if len(set(cfg['public_files']+cfg['private_files'])) != len(cfg['public_files']+cfg['private_files']):
        raise DataError('duplicate_data_path')
    return cfg


def files(cfg):
    return cfg['public_files'] + cfg['private_files']


def hashes(root, names):
    result = {}
    for name in names:
        p = Path(root)/name
        if p.is_symlink() or not p.is_file():
            raise DataError('missing_or_nonregular_data_file:' + name)
        result[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def copy_data(source, target, cfg):
    for name in files(cfg):
        src, dst = Path(source)/name, Path(target)/name
        if src.is_symlink() or not src.is_file():
            raise DataError('missing_or_nonregular_data_file:' + name)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def owner(name):
    leaf = Path(name).name
    if leaf.startswith('reports_') or leaf == 'reports.json':
        return 'reports'
    if leaf.startswith('macro_') or leaf == 'macro.json':
        return 'macro'
    return 'news'
