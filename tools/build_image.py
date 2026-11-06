"""Build a UBI image in a NEW Linux directory. Never opens any flash device."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tarfile
from patch_airplay import patch

SOURCE_TAR_SHA = '22e13e2b765595aa2ad5ad50df202e924fcf4b0bceb503416053b47642e98d7a'
DHCP_SHA = 'bddafb863e3f37da68fc680db389f0c1b4c5fd0468953580f0f4422726c382d7'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def inventory(root):
    rows = {}
    for p in sorted(root.rglob('*')):
        s = p.lstat()
        row = {'mode': s.st_mode, 'uid': s.st_uid, 'gid': s.st_gid}
        if p.is_symlink():
            row.update(type='symlink', target=os.readlink(p))
        elif p.is_file():
            row.update(type='file', bytes=s.st_size, sha256=sha(p))
        elif p.is_dir():
            row.update(type='directory')
        else:
            raise ValueError('Unsupported special entry: ' + str(p))
        rows[p.relative_to(root).as_posix()] = row
    return rows

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-tar', type=Path, required=True)
    ap.add_argument('--build-dir', type=Path, required=True)
    args = ap.parse_args()
    assert os.geteuid() == 0, 'Linux root is needed to preserve vendor file ownership'
    source = args.source_tar.resolve()
    build = args.build_dir.absolute()
    assert sha(source) == SOURCE_TAR_SHA, 'Use the documented exact donor extraction'
    repo = Path(__file__).resolve().parents[1]
    assert sha(repo / 'firmware/bin/udhcpd') == DHCP_SHA
    build.mkdir(parents=True, exist_ok=False)
    root = build / 'root'
    root.mkdir()
    commands = []
    def run(argv):
        argv = [str(x) for x in argv]
        r = subprocess.run(argv, capture_output=True, text=True)
        commands.append({'argv': argv, 'returncode': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr})
        (build / 'commands.json').write_text(json.dumps(commands, indent=2))
        if r.returncode:
            raise RuntimeError(r.stdout + r.stderr)
        return r.stdout
    run(['tar', '--numeric-owner', '--same-owner', '-xpf', source, '-C', root])
    before = inventory(root)
    overlay = repo / 'firmware/overlay'
    for p in sorted(overlay.rglob('*')):
        if not p.is_file():
            continue
        rel = p.relative_to(overlay)
        dest = root / rel
        assert not dest.is_symlink()
        previous = dest.stat() if dest.exists() else None
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(p.read_bytes())
        dest.chmod(stat.S_IMODE(previous.st_mode) if previous else (0o755 if p.suffix == '.sh' else 0o644))
        os.chown(dest, previous.st_uid if previous else 0, previous.st_gid if previous else 0)
        if p.suffix == '.sh' or p.name in ('rcS', 'profile'):
            run(['/bin/sh', '-n', dest])
    for rel, target in json.loads((repo / 'firmware/links.json').read_text()).items():
        dest = root / rel
        assert dest.is_file() and not dest.is_symlink()
        dest.unlink()
        dest.symlink_to(target)
        os.lchown(dest, 0, 0)
    air = root / 'usr/lib/libAirPlay.so'
    air.write_bytes(patch(air.read_bytes()))
    dhcp = root / 'usr/libexec/carplay-revival/udhcpd'
    dhcp.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repo / 'firmware/bin/udhcpd', dhcp)
    dhcp.chmod(0o755)
    os.chown(dhcp, 0, 0)
    after = inventory(root)
    changes = [{'path': p, 'before': before.get(p), 'after': after.get(p)}
               for p in sorted(before.keys() | after.keys()) if before.get(p) != after.get(p)]
    (build / 'inventory.json').write_text(json.dumps(after, indent=2))
    (build / 'changes.json').write_text(json.dumps(changes, indent=2))
    image = build / 'rootfs.ubifs'
    run(['mkfs.ubifs', '-r', root, '-m', '2048', '-e', '126976', '-c', '848',
         '-j', '8388608', '-x', 'lzo', '-f', '8', '-F', '-k', 'r5', '-p', '1',
         '-l', '5', '-o', image, '-v'])
    # Keep the original flash geometry and partition; reserve enough LEBs for
    # the rebuilt contents. The new DHCP binary may require one additional LEB.
    volume_bytes = image.stat().st_size
    assert volume_bytes % 126976 == 0
    assert volume_bytes // 126976 <= 840, 'Exceeds conservative rootfs LEB budget'
    config = build / 'ubinize.ini'
    config.write_text('[rootfs]\nmode=ubi\nimage=' + str(image) + '\nvol_type=dynamic\n'
        'vol_flags=autoresize\nvol_id=0\nvol_name=rootfs\nvol_alignment=1\nvol_size=' + str(volume_bytes) + '\n')
    run(['ubinize', '-o', build / 'rootfs.img', '-p', '131072', '-m', '2048', '-s', '2048',
         '-O', '2048', '-x', '1', '-Q', '24958429', config])
    assert (build / 'rootfs.img').stat().st_size < 106 * 1024 * 1024
    summary = {'release': '2026.11-w3-rc1', 'source_tar_sha256': sha(source),
        'rootfs_sha256': sha(build / 'rootfs.img'), 'rootfs_bytes': (build / 'rootfs.img').stat().st_size,
        'changed_paths': [r['path'] for r in changes], 'settings_migration': False,
        'diagnostic_logger_bundled': False, 'complete_image_vehicle_tested': False,
        'device_writes': False,
        'versions': {name: run([name, '--version']).splitlines()[0] for name in ('mkfs.ubifs', 'ubinize', 'tar')}}
    (build / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
