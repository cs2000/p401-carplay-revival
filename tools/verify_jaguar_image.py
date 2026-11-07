#!/usr/bin/env python3
"""Independently check the Jaguar image, full filesystem delta and USB archive.

Consumes a metadata-preserving roundtrip made by archive_ubi_tree.py. Checks are
offline and do not prove board compatibility, a cold boot or flash recovery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import tarfile
import zipfile
import zlib

from image_checks import dependencies, medium
from verify_usb import verify as verify_usb

REPO = Path(__file__).resolve().parents[1]
BASE_TAR_SHA = 'be982d06fdefbc91229cd9d72081ac47f08ac3dc9733fcfa8aac02af10ee1b56'
BASE_IMAGE_SHA = 'f0a56487359a94c556fc4bd38026b648b98d6ee55a94ccef8d3512a299537e4d'
UI_SHA = 'c62c2d49d3ce423d9cf11d96325e7ee5e50d7967ce0a865b2cf6f3a6f6593639'
UI_ROOT = 'usr/libexec/carplay-revival/ui'
LIBRARY = UI_ROOT + '/libp401-ui.so'
COMPATIBILITY = UI_ROOT + '/compatibility.txt'
RUNNER = UI_ROOT + '/run-ui.sh'
HELPER = 'usr/libexec/carplay-revival/verify'
ALLOWED = {'etc/profile', HELPER, UI_ROOT, LIBRARY, COMPATIBILITY, RUNNER}
ABI_PATHS = {'/usr/bin/MsnCoreApp', '/usr/lib/libBlueTooth.so', '/usr/lib/libLauncher-Box.so',
             '/usr/lib/libSetting.so', '/usr/lib/libMsnCommons.so',
             '/usr/local/Qt4.7.4/lib/libQtCore.so.4.7.4',
             '/usr/local/Qt4.7.4/lib/libQtGui.so.4.7.4',
             '/lib/libstdc++.so.6', '/lib/libc.so.6'}
W3_PINS = {
    'usr/lib/libAirPlay.so': '551112f2b5e525a0ff4994357ee1563c5d1e1dad56f59df6724962a0be8e34db',
    'usr/libexec/carplay-revival/udhcpd': 'bddafb863e3f37da68fc680db389f0c1b4c5fd0468953580f0f4422726c382d7',
}
BOOT_PINS = {
    'update': (20, 'fd4c7328b55789ea720829f7983ba47ca6342096da4bf9ce2f06136ad667679e'),
    'zImage': (3255848, '04dc369f6fa30443a5c4353467cb5f8994af3a95798824e3f2815d360a46f9fc'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name:
        raise ValueError('Unsafe filesystem path: ' + name)
    return path.as_posix()


def tar_inventory(path):
    """Match build_image.inventory, including all numeric ownership and modes."""
    rows = {}
    with tarfile.open(path) as archive:
        for member in archive:
            name = safe_path(member.name)
            if name == '.':
                continue
            if name in rows:
                raise ValueError('Duplicate tar path: ' + name)
            row = {'uid': member.uid, 'gid': member.gid}
            if member.isfile() or member.islnk():
                payload = archive.extractfile(member).read()
                row.update(type='file', mode=stat.S_IFREG | member.mode,
                           bytes=len(payload), sha256=digest(payload))
            elif member.isdir():
                row.update(type='directory', mode=stat.S_IFDIR | member.mode)
            elif member.issym():
                row.update(type='symlink', mode=stat.S_IFLNK | member.mode, target=member.linkname)
            else:
                raise ValueError('Unexpected special tar path: ' + name)
            rows[name] = row
    return rows


def tar_root(path):
    with tarfile.open(path) as archive:
        roots = [item for item in archive if safe_path(item.name) == '.']
        if len(roots) != 1 or not roots[0].isdir():
            raise ValueError('Expected one root directory tar record')
        item = roots[0]
        return {'type': 'directory', 'mode': stat.S_IFDIR | item.mode,
                'uid': item.uid, 'gid': item.gid}


def metadata_inventory(path):
    document = json.loads(path.read_text())
    rows = {}
    for entry in document['entries']:
        name = safe_path(entry['path'])
        if name == '.':
            continue
        if name in rows:
            raise ValueError('Duplicate metadata path: ' + name)
        kind = 'file' if entry['type'] == 'hardlink' else entry['type']
        row = {key: entry[key] for key in ('mode', 'uid', 'gid')}
        row['type'] = kind
        if kind == 'file':
            row.update(bytes=entry['size'], sha256=entry['sha256'])
        elif kind == 'symlink':
            row['target'] = entry['target']
        elif kind != 'directory':
            raise ValueError('Unexpected special image path: ' + name)
        if entry.get('xattrs'):
            raise ValueError('Unsupported xattrs: ' + name)
        rows[name] = row
    return document, rows


def validate(build, roundtrip, base_tar, output, manifest_path=None, usb_root=None):
    checks = []
    completed = False
    report = {}

    def check(label, value):
        checks.append({'check': label, 'passed': bool(value)})
        print(('PASS ' if value else 'FAIL ') + label, flush=True)
        if not value:
            raise AssertionError(label)

    try:
        base_bytes = base_tar.read_bytes()
        check('base tar is the pinned metadata-preserving public RC1 extraction', digest(base_bytes) == BASE_TAR_SHA)
        base = tar_inventory(base_tar)
        expected = json.loads((build / 'inventory.json').read_text())
        summary = json.loads((build / 'summary.json').read_text())
        image = build / 'rootfs.img'
        image_sha = digest(image.read_bytes())
        check('builder summary pins the image being checked',
              summary['rootfs_sha256'] == image_sha and summary['rootfs_bytes'] == image.stat().st_size)
        check('builder used the pinned RC1 base and exact owner-tested UI',
              summary['source_tar_sha256'] == BASE_TAR_SHA and summary['library_sha256'] == UI_SHA)
        metadata, actual = metadata_inventory(roundtrip / 'rootfs_metadata.json')
        archive = roundtrip / 'rootfs_source_tree.tar'
        tar_rows = tar_inventory(archive)
        check('roundtrip belongs to the exact new image', metadata['source_sha256'] == image_sha)
        roots = [entry for entry in metadata['entries'] if safe_path(entry['path']) == '.']
        check('root directory metadata is unchanged from public RC1 and agrees with roundtrip tar',
              len(roots) == 1 and {key: roots[0][key] for key in ('type', 'mode', 'uid', 'gid')} ==
              tar_root(base_tar) == tar_root(archive))
        check('complete roundtrip tar matches extracted UBI metadata', tar_rows == actual)
        check('complete image inventory matches builder (paths/type/mode/uid/gid/content/links)', actual == expected)
        changes = sorted(path for path in base.keys() | actual.keys() if base.get(path) != actual.get(path))
        check('only the exact six reviewed Jaguar paths differ from public RC1', set(changes) == ALLOWED)
        check('builder delta agrees with independently compared filesystem', summary['changed_paths'] == changes)
        check('no baseline file or directory was deleted', base.keys() <= actual.keys())
        check('persistent userdata and all other factory paths remain unchanged',
              not any(path == 'data' or path.startswith('data/') for path in changes))
        check('profile retains vendor type/mode/owner/group',
              all(actual['etc/profile'][key] == base['etc/profile'][key] for key in ('type', 'mode', 'uid', 'gid')))
        for path, mode in [(UI_ROOT, stat.S_IFDIR | 0o755), (LIBRARY, stat.S_IFREG | 0o644),
                           (COMPATIBILITY, stat.S_IFREG | 0o644), (RUNNER, stat.S_IFREG | 0o755),
                           (HELPER, stat.S_IFREG | 0o755)]:
            check('new rootfs permissions and numeric owner: ' + path,
                  actual[path]['mode'] == mode and actual[path]['uid'] == 0 and actual[path]['gid'] == 0)
        for name in ('MsnProductInfo.ini', 'FactoryConfig.ini'):
            row = actual['msnprofile/' + name]
            check('existing persistent settings alias retained: ' + name,
                  row['type'] == 'symlink' and row['target'] == '/data/msncfg/' + name)
        for path, pinned in {LIBRARY: UI_SHA, **W3_PINS}.items():
            check('exact unchanged component: ' + path, actual[path]['sha256'] == pinned)
        with tarfile.open(archive) as tf:
            read = lambda path: tf.extractfile(path).read()
            manifest = read(COMPATIBILITY)
            wrapper = read(RUNNER)
            profile = read('etc/profile')
            crc_length = lambda data: f'{zlib.crc32(data):08x} {len(data)}'.encode('ascii')
            check('exact wrapper is CRC-pinned at the original profile launch point', crc_length(wrapper) in profile)
            check('compatibility manifest is CRC-pinned by the exact wrapper', crc_length(manifest) in wrapper)
            parsed = [line.decode('ascii').split(' ', 2) for line in manifest.splitlines()]
            check('compatibility manifest pins UI, nine vendor ABI files and static verifier',
                  len(parsed) == 11 and parsed[0][2] == '/' + LIBRARY and parsed[-1][2] == '/' + HELPER and
                  {row[2] for row in parsed} == ABI_PATHS | {'/' + LIBRARY, '/' + HELPER})
            for crc, size, path in parsed:
                safe_path(path.lstrip('/'))
                check('manifest matches actual installed bytes: ' + path,
                      path.startswith('/') and crc_length(read(path.lstrip('/'))) == (crc + ' ' + size).encode('ascii'))
            check('production startup is independent of field-W3/logging paths',
                  all(value not in profile + wrapper for value in
                      (b'/data/p401-w3', b'/usr/lib/p401-r4', b'p401-log-stream', b'p401-w3-install-ok')))
        report['media'] = medium(image)
        check('image CRCs and conservative UBI/UBIFS geometry pass',
              report['media']['superblock']['min_io_size'] == 2048 and
              report['media']['superblock']['leb_size'] == 126976 and
              report['media']['superblock']['max_leb_cnt'] == 848 and image.stat().st_size < 106 * 1024 * 1024)
        report['dependencies'] = dependencies(archive, extra_seeds=(LIBRARY, HELPER))
        check('ARM dependency closure includes installed UI preload and verifier',
              not report['dependencies']['missing'] and LIBRARY in report['dependencies']['files'] and
              HELPER in report['dependencies']['files'])
        usb = usb_root or build / 'usb'
        manifest_document = json.loads(manifest_path.read_text()) if manifest_path else summary
        check('USB verifier accepts the exact three image files', verify_usb(usb, manifest_document))
        check('USB has only the kernel/filesystem update files', {p.name for p in usb.iterdir()} == {'update', 'zImage', 'rootfs.img'})
        for name, pin in BOOT_PINS.items():
            data = (usb / name).read_bytes()
            check('unchanged public RC1 boot payload: ' + name, (len(data), digest(data)) == pin)
        check('USB rootfs is the exact fully checked new image', digest((usb / 'rootfs.img').read_bytes()) == image_sha)
        download = manifest_document['download']
        zip_path = build / download['name']
        zip_bytes = zip_path.read_bytes()
        check('download archive size/SHA match manifest', len(zip_bytes) == download['bytes'] and digest(zip_bytes) == download['sha256'])
        with zipfile.ZipFile(zip_path) as z:
            check('ZIP CRCs and exact three-file safe content', z.testzip() is None and
                  len(z.namelist()) == 3 and set(z.namelist()) == {'update', 'zImage', 'rootfs.img'})
            check('ZIP contents are the exact verified USB payload',
                  all(z.read(name) == (usb / name).read_bytes() for name in z.namelist()))
        check('new full image is not labelled vehicle/recovery proven',
              summary['complete_image_vehicle_tested'] is False and summary['full_flash_recovery_proven'] is False)
        report.update(library_sha256=UI_SHA, rootfs_sha256=image_sha, base_image_sha256=BASE_IMAGE_SHA,
                      changed_paths=changes, complete_inventory_matches=True, usb_payload_verified=True)
        completed = True
    finally:
        report.update(passed=completed and bool(checks) and all(row['passed'] for row in checks),
                      checks=checks, count=len(checks),
                      scope='Fresh offline UBI/UBIFS checks, complete numeric filesystem inventory comparison, ARM ELF closure and exact ZIP/USB verification. No target kernel boot, radio/MCU operation, physical reboot, flash installation or unbootable-unit recovery test.',
                      complete_image_vehicle_tested=False, full_flash_recovery_proven=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', required=True, type=Path)
    parser.add_argument('--roundtrip-dir', required=True, type=Path)
    parser.add_argument('--base-tar', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--manifest', type=Path, help='Published manifest; defaults to builder summary')
    parser.add_argument('--usb-root', type=Path, help='Extracted download to check; defaults to build-dir/usb')
    args = parser.parse_args()
    result = validate(args.build_dir, args.roundtrip_dir, args.base_tar, args.output, args.manifest, args.usb_root)
    print(json.dumps({key: result[key] for key in ('passed', 'count', 'rootfs_sha256', 'complete_inventory_matches')}, indent=2))
