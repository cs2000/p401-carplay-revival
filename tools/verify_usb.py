"""Read-only verification of an extracted three-file USB payload."""
import argparse
import hashlib
import json
from pathlib import Path

def verify(root, manifest):
    expected = {x['name']: x for x in manifest['usb_files']}
    if set(expected) != {'update', 'zImage', 'rootfs.img'}:
        raise ValueError('Manifest must describe exactly the three update files')
    forbidden = {'msn_autocopy', 'msn_factory_configs', 'UpConfig', 'userdata.img',
                 'uboot.bin', 'nboot.bin', 'P401_LOGS.ENABLE'}
    present = {p.name.casefold() for p in root.iterdir()}
    if present & {s.casefold() for s in forbidden}:
        raise ValueError('Mixed update/configuration/logger files found; use a clean USB')
    for name, row in expected.items():
        data = (root / name).read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Size/SHA256 mismatch: ' + name)
    if (root / 'update').read_bytes() != b'kernel\r\nfilesystem\r\n':
        raise ValueError('Unexpected update selector')
    return True

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('usb_root', type=Path)
    p.add_argument('--manifest', type=Path, default=Path(__file__).resolve().parents[1] /
                   'releases/2026.11-w3-rc1/manifest.json')
    args = p.parse_args()
    verify(args.usb_root, json.loads(args.manifest.read_text()))
    print('PASS: exact kernel/filesystem payload; no conflicting installer files. No files written.')
