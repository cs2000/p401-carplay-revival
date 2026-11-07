"""Verify a new UI1 candidate with ARM shell/CRC and isolated process fixtures.

No vendor service is started. Original packages and historical evidence are read-only.
Run in the prepared toolchain container, with QEMU and the extracted vendor root.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shlex
import subprocess
import tempfile
import zipfile
import zlib

UI = Path(__file__).resolve().parents[2]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def crc(data):
    return f'{zlib.crc32(data):08x} {len(data)}'


def validate(candidate, vendor, output):
    checks = []

    def check(label, ok):
        checks.append({'check': label, 'passed': bool(ok)})
        print(('PASS ' if ok else 'FAIL ') + label, flush=True)
        assert ok, label

    def archive(name):
        with zipfile.ZipFile(candidate / name) as z:
            check(name + ' ZIP integrity', z.testzip() is None)
            names = [i.filename for i in z.infolist() if not i.is_dir()]
            check(name + ' unique safe autocopy paths', len(names) == len(set(names)) and all(n.startswith('msn_autocopy/') and '..' not in Path(n).parts for n in names))
            return {n.removeprefix('msn_autocopy/'): z.read(n) for n in names}

    install = archive('INSTALL.zip')
    rollback = archive('ROLLBACK.zip')
    expected = {'data/carplay-revival/lib/libp401-ui.so', 'data/carplay-revival/compatibility.txt', 'data/carplay-revival/run-ui.sh', 'data/carplay-revival/state', 'usr/bin/p401-recovery-run-core.sh', 'data/p401-w3/install-checks.txt'}
    check('exact six-file GUI-only installer', set(install) == expected)
    check('exact three-file rollback', set(rollback) == {'data/carplay-revival/state', 'usr/bin/p401-recovery-run-core.sh', 'data/p401-w3/install-checks.txt'})
    check('original rollback archive byte-for-byte', (candidate / 'ROLLBACK.zip').read_bytes() == (UI / 'packages/ROLLBACK.zip').read_bytes())
    for name, data in rollback.items():
        check('rollback baseline ' + name, data == (UI / 'baseline' / name).read_bytes())
    old = (UI / 'baseline/data/p401-w3/install-checks.txt').read_text().splitlines()
    new = install['data/p401-w3/install-checks.txt'].decode().splitlines()
    changed = [(a, b) for a, b in zip(old, new) if a != b]
    check('W3 manifest changes only GUI runner', len(old) == len(new) and len(changed) == 1 and all(x.endswith(' /usr/bin/p401-recovery-run-core.sh') for x in changed[0]))
    check('GUI runner row pins exact new bytes', crc(install['usr/bin/p401-recovery-run-core.sh']) + ' /usr/bin/p401-recovery-run-core.sh' in new)
    check('new wrapper CRC pinned by GUI runner', crc(install['data/carplay-revival/run-ui.sh']) in install['usr/bin/p401-recovery-run-core.sh'].decode())
    check('installer enabled and rollback disabled', install['data/carplay-revival/state'] == b'enabled\n' and rollback['data/carplay-revival/state'] == b'disabled\n')
    check('wrapper pins compatibility bytes', crc(install['data/carplay-revival/compatibility.txt']) in install['data/carplay-revival/run-ui.sh'].decode())
    shell = ['qemu-arm', '-L', str(vendor), str(vendor / 'bin/busybox'), 'sh']
    verifier = ['qemu-arm', str(UI / 'lab/reference/p401-diag')]

    with tempfile.TemporaryDirectory(prefix='ui1-delivery-', dir=UI / 'build/cloud') as temporary:
        f = Path(temporary)

        def write(path, data):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data.encode() if isinstance(data, str) else data)
            path.chmod(0o755)

        for name, data in install.items():
            write(f / 'payload' / name, data)
            if name.endswith('.sh'):
                check('ARM shell syntax ' + name, subprocess.run(shell + ['-n', str(f / 'payload' / name)], capture_output=True).returncode == 0)
        rows = []
        library = f / 'fixture/data/carplay-revival/lib/libp401-ui.so'
        write(library, install['data/carplay-revival/lib/libp401-ui.so'])
        for line in install['data/carplay-revival/compatibility.txt'].decode().splitlines():
            checksum, size, absolute = line.split(' ', 2)
            path = library if absolute.endswith('/libp401-ui.so') else vendor / absolute.lstrip('/')
            check('ARM CRC verifies ' + absolute, path.is_file() and subprocess.run(verifier + ['verify', str(path), checksum, size], capture_output=True).returncode == 0)
            rows.append(f'{checksum} {size} {path}\n')
        fixture_manifest = ''.join(rows).encode()
        fixture = f / 'fixture'
        data = fixture / 'data/carplay-revival'
        tmp = fixture / 'tmp'
        tmp.mkdir(parents=True)
        write(fixture / 'helper', '#!/bin/sh\nexec ' + shlex.join(verifier) + ' "$@"\n')
        write(fixture / 'bin/MsnCoreApp', '''#!/bin/sh
if [ -n "$P401_TEST_PRELOAD" ]; then
    echo CUSTOM
    case "$CASE" in
        crash) exit 139;;
        notready) exit 0;;
        timeout) exec sleep 8;;
        *) echo ready > "$FIXTURE/tmp/p401-ui-ready"; exit 0;;
    esac
else
    echo STOCK
fi
''')
        script = install['data/carplay-revival/run-ui.sh'].decode()
        script = script.replace('/data/carplay-revival', str(data)).replace('/usr/lib/p401-r4/p401-diag', str(fixture / 'helper')).replace('/tmp/p401-', str(tmp / 'p401-'))
        script = script.replace(crc(install['data/carplay-revival/compatibility.txt']), crc(fixture_manifest))
        # Record launches instead of loading vendor Qt into a host recorder.
        # Only the test watchdog interval is shortened (60 seconds -> 2).
        script = script.replace('LD_PRELOAD=', 'P401_TEST_PRELOAD=').replace('[ "$ticks" -lt 60 ]', '[ "$ticks" -lt 2 ]')
        write(fixture / 'run-ui.sh', script)
        profile = fixture / 'msnprofile/MsnProductInfo.ini'
        profile_bytes = b'[General]\nMcuType=7\nBlueToothType=3\nWlanType=1\n'
        for case in ['healthy', 'disabled', 'no-w3', 'corrupt-manifest', 'corrupt-library', 'incompatible-vendor', 'crash', 'notready', 'timeout']:
            for path in tmp.glob('p401-*'):
                path.unlink()
            write(data / 'state', 'disabled\n' if case == 'disabled' else 'enabled\n')
            write(tmp / 'p401-w3-install-ok', 'verified\n')
            if case == 'no-w3':
                (tmp / 'p401-w3-install-ok').unlink()
            manifest = fixture_manifest
            if case == 'incompatible-vendor':
                # Valid manifest checksum, deliberately invalid vendor row.
                manifest = manifest.replace(rows[1].encode(), ('00000000 1 ' + rows[1].split(' ', 2)[2]).encode())
            write(data / 'compatibility.txt', b'bad manifest\n' if case == 'corrupt-manifest' else manifest)
            case_script = script.replace(crc(fixture_manifest), crc(manifest)) if case == 'incompatible-vendor' else script
            write(fixture / 'run-ui.sh', case_script)
            write(library, b'corrupt' if case == 'corrupt-library' else install['data/carplay-revival/lib/libp401-ui.so'])
            write(profile, profile_bytes)
            env = dict(os.environ, PATH=str(fixture / 'bin') + ':' + os.environ['PATH'], CASE=case, FIXTURE=str(fixture))
            env.pop('LD_PRELOAD', None)
            env.pop('P401_UI_LAB', None)
            result = subprocess.run(shell + [str(fixture / 'run-ui.sh')], env=env, capture_output=True, timeout=20)
            text = result.stdout.decode()
            custom, stock = 'CUSTOM' in text, 'STOCK' in text
            if case == 'healthy':
                ok = custom and not stock and (data / 'state').read_bytes() == b'enabled\n'
            elif case in ['crash', 'notready', 'timeout']:
                ok = custom and stock and (data / 'state').read_bytes() == b'disabled\n'
            else:
                ok = stock and not custom
            check(case + ' launch/fallback', result.returncode == 0 and ok)
            check(case + ' preserves factory profile', profile.read_bytes() == profile_bytes)
    report = {'passed': True, 'library_sha256': digest(install['data/carplay-revival/lib/libp401-ui.so']), 'installer_sha256': digest((candidate / 'INSTALL.zip').read_bytes()), 'checks': checks, 'scope': 'Fresh actual ARM BusyBox/CRC checks, archive validation and redirected process fixtures. Shortened watchdog only in fixture. Unchanged W3 rows preserved, not a fresh validation of unavailable field logging payloads. No vendor services, physical radio, MCU, reboot or flash test.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--vendor-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    validate(args.candidate.resolve(), args.vendor_root.resolve(), args.output.resolve())
