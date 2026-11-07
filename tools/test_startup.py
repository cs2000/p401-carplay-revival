"""Exercise settings preservation with native ARM BusyBox in disposable fixtures."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
import zlib

UI_PREFIX = 'usr/libexec/carplay-revival/ui'
UI_SHA = 'c62c2d49d3ce423d9cf11d96325e7ee5e50d7967ce0a865b2cf6f3a6f6593639'
RC2_HELPER_SHA = '033ccce487a5f2631ccf4ffde32b77e565c6452e4a730ac9873cead6bf728a48'
VENDOR_ABI_PATHS = {'/usr/bin/MsnCoreApp', '/usr/lib/libBlueTooth.so', '/usr/lib/libLauncher-Box.so',
                    '/usr/lib/libSetting.so', '/usr/lib/libMsnCommons.so',
                    '/usr/local/Qt4.7.4/lib/libQtCore.so.4.7.4',
                    '/usr/local/Qt4.7.4/lib/libQtGui.so.4.7.4',
                    '/lib/libstdc++.so.6', '/lib/libc.so.6'}
RC2_EXTRA_ABI_PINS = {
    'usr/lib/libLinkLibs.so': {
        'bytes': 129180, 'crc32': '59ed7170',
        'sha256': 'ac7d73df4bdd7dfa59e4042dbf46c19797eb3ce84cca630dff79308911e8acdc',
    },
}


def rc2_native_evidence(data):
    """Validate completed evidence and return its exact file/library identity."""
    document = json.loads(data)
    if not isinstance(document, dict) or document.get('passed') is not True or document.get('complete') is not True:
        raise ValueError('RC2 native evidence must be passed and complete')
    library_sha = document.get('library_sha256')
    if not isinstance(library_sha, str) or not re.fullmatch('[0-9a-f]{64}', library_sha) or library_sha == UI_SHA:
        raise ValueError('RC2 evidence must identify a new ARM library SHA256')
    cases = document.get('cases')
    if not isinstance(cases, list) or not cases or any(not isinstance(case, dict) or case.get('passed') is not True for case in cases):
        raise ValueError('RC2 native evidence needs nonempty passed cases')
    snapshot = document.get('source_snapshot', {})
    files = snapshot.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('RC2 native evidence needs a production source snapshot')
    snapshot_sha = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if snapshot.get('sha256') != snapshot_sha:
        raise ValueError('RC2 production source snapshot hash does not match its files map')

    def inspect(value):
        if isinstance(value, dict):
            if 'passed' in value and value['passed'] is not True:
                raise ValueError('RC2 native evidence contains a failed or incomplete check')
            if 'library_sha256' in value and value['library_sha256'] != library_sha:
                raise ValueError('RC2 native evidence contains results for another library')
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)
    inspect(document)
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'library_sha256': library_sha,
            'source_snapshot_sha256': snapshot_sha}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--variant', choices=('rc1', 'jaguar', 'rc2'), default='rc1',
                    help='rc1: clean W3 RC1; jaguar: exact Jaguar RC1; rc2: newly validated Jaguar RC2')
    ap.add_argument('--ui-evidence', type=Path, help='Required for rc2: complete passed native evidence for its exact UI library')
    ap.add_argument('--summary', type=Path, help='RC2 builder summary; defaults to root/../summary.json')
    a = ap.parse_args()
    if a.variant == 'rc2' and a.ui_evidence is None:
        ap.error('--variant rc2 requires --ui-evidence')
    if a.variant != 'rc2' and (a.ui_evidence is not None or a.summary is not None):
        ap.error('--ui-evidence and --summary are only used with --variant rc2')
    root = a.root.resolve()
    qemu = ['/usr/bin/qemu-arm', '-cpu', 'cortex-a7', '-L', str(root), str(root / 'bin/busybox')]
    checks = []
    completed = False
    ui_evidence = None
    expected_ui_sha = UI_SHA
    def check(label, ok):
        checks.append({'check': label, 'passed': bool(ok)})
        if not ok:
            raise AssertionError(label)
    def run(argv, **kw):
        return subprocess.run(argv, capture_output=True, text=True, timeout=30, **kw)
    def digest(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()
    try:
        if a.variant == 'rc2':
            ui_evidence = rc2_native_evidence(a.ui_evidence.read_bytes())
            expected_ui_sha = ui_evidence['library_sha256']
            summary = json.loads((a.summary or root.parent / 'summary.json').read_text())
            check('RC2 builder summary identifies the exact newly native-validated UI',
                  summary['release'] == '2026.11-jaguar-xfr-rc2' and summary['library_sha256'] == expected_ui_sha)
            check('RC2 builder pins the exact complete native evidence file',
                  all(summary['ui_native_evidence'].get(key) == value for key, value in ui_evidence.items()))
            check('RC2 has no inherited owner/full-image/recovery test claim',
                  summary['owner_tested_ui_binary_unchanged'] is False and
                  summary['complete_image_vehicle_tested'] is False and summary['full_flash_recovery_proven'] is False)
            check('RC2 summary pins the exact native connection provider', summary['extra_abi_pins'] == RC2_EXTRA_ABI_PINS)
        for rel in ('etc/profile', 'etc/rc.d/rcS', 'etc/hostapd.sh', 'usr/bin/carplay-revival-check-settings.sh'):
            r = run(qemu + ['sh', '-n', str(root / rel)])
            check('ARM shell syntax: ' + rel, r.returncode == 0)
        with tempfile.TemporaryDirectory(prefix='revival-startup-') as td:
            fixture = Path(td)
            tools = fixture / 'tools'
            tools.mkdir()
            for app in ('cat', 'grep'):
                wrapper = tools / app
                wrapper.write_text('#!/bin/sh\nexec ' + shlex.join(qemu + [app]) + ' "$@"\n')
                wrapper.chmod(0o755)
            env = dict(os.environ, PATH=str(tools))
            (fixture / 'data/msncfg').mkdir(parents=True)
            (fixture / 'tmp').mkdir()
            mode = fixture / 'tmp/p401-data-mode'
            mode.write_text('persistent\n')
            src = (root / 'usr/bin/carplay-revival-check-settings.sh').read_text()
            src = re.sub(r'/(data|tmp)/', lambda m: str(fixture) + m.group(0), src)
            guard = fixture / 'check.sh'
            guard.write_text(src)
            product = fixture / 'data/msncfg/MsnProductInfo.ini'
            factory = fixture / 'data/msncfg/FactoryConfig.ini'
            for mcu in (7, 6, 0, 12):
                product.write_text('[General]\nMcuType=' + str(mcu) + '\nScreenType=5\nUnknownCalibration=keep\n')
                factory.write_text('[General]\nIphoneLinkType=1\nVolume=37\nDisableSetMCUType=0\n[Other]\nValue=preserve\n')
                hashes = (digest(product), digest(factory))
                r = run(qemu + ['sh', str(guard)], env=env)
                if r.returncode:
                    print(r.stdout + r.stderr)
                check(f'MCU {mcu}: existing settings accepted without selecting a type', r.returncode == 0)
                check(f'MCU {mcu}: all configuration bytes unchanged (USB-only included)',
                      hashes == (digest(product), digest(factory)))
            mode.write_text('volatile\n')
            check('RAM fallback rejected', run(qemu + ['sh', str(guard)], env=env).returncode != 0)
            mode.write_text('persistent\n')
            saved = factory.read_bytes()
            factory.unlink()
            check('missing factory file rejected', run(qemu + ['sh', str(guard)], env=env).returncode != 0)
            check('missing factory file not created', not factory.exists())
            factory.write_bytes(b'')
            check('empty factory file rejected', run(qemu + ['sh', str(guard)], env=env).returncode != 0)
            factory.write_text('[NotGeneral]\nValue=1\n')
            check('invalid configuration section rejected', run(qemu + ['sh', str(guard)], env=env).returncode != 0)
            factory.write_bytes(saved)
            product.write_bytes(b'[gEnErAl]\r\nMcuType=6\r\n')
            check('case-insensitive CRLF configuration accepted', run(qemu + ['sh', str(guard)], env=env).returncode == 0)

        for name in ('MsnProductInfo.ini', 'FactoryConfig.ini'):
            p = root / 'msnprofile' / name
            check('rootfs profile aliases existing userdata: ' + name,
                  p.is_symlink() and os.readlink(p) == '/data/msncfg/' + name)
        rc = (root / 'etc/rc.d/rcS').read_text()
        profile = (root / 'etc/profile').read_text()
        check('no configuration migration or recovery call',
              all(s not in rc + profile for s in ('p401-prepare.sh', 'p401-recover-mcu.sh', 'p401-run-core.sh')))
        check('no automatic erase/format/environment write in startup',
              all(s not in rc for s in ('flash_erase', 'ubimkvol', 'fw_setenv', 'ubiformat')))
        check('no diagnostic helpers installed', not any(root.glob('usr/bin/p401-*.sh')) and not (root / 'usr/lib/p401-r4').exists())
        service = (root / 'usr/share/dbus-1/services/com.arkmicro.carplay.service').read_text()
        check('direct native CarPlay D-Bus activation', 'Exec=/usr/bin/carplay\n' in service)
        if a.variant == 'rc1':
            check('direct vendor GUI launch', 'MsnCoreApp -qws&' in profile)
        else:
            wrapper = root / UI_PREFIX / 'run-ui.sh'
            compatibility = root / UI_PREFIX / 'compatibility.txt'
            library = root / UI_PREFIX / 'libp401-ui.so'
            helper = root / 'usr/libexec/carplay-revival/verify'
            text = wrapper.read_text()
            check('ARM shell syntax: dedicated Jaguar UI launcher',
                  run(qemu + ['sh', '-n', str(wrapper)]).returncode == 0)
            check('Jaguar uses the exact owner-tested ARM UI library' if a.variant == 'jaguar' else
                  'Jaguar RC2 uses the exact newly native-validated ARM UI library', digest(library) == expected_ui_sha)
            if a.variant == 'rc2':
                check('RC2 retains the exact verified static ARM integrity helper', digest(helper) == RC2_HELPER_SHA)
                for path, pin in RC2_EXTRA_ABI_PINS.items():
                    provider = root / path
                    check('RC2 retains exact native connection provider: ' + path,
                          provider.stat().st_size == pin['bytes'] and digest(provider) == pin['sha256'])
            check('dedicated Jaguar launcher is CRC-gated from profile',
                  '/' + UI_PREFIX + '/run-ui.sh' in profile and
                  '/usr/libexec/carplay-revival/verify' in profile and
                  f'{zlib.crc32(wrapper.read_bytes()):08x} {wrapper.stat().st_size}' in profile)
            check('existing settings guard precedes all vendor initialization',
                  profile.index('carplay-revival-check-settings.sh') < profile.index('MsnFirstInit'))
            check('UI integration has no field-W3 or logger prerequisites',
                  all(s not in profile + text for s in
                      ('/data/p401-w3', '/usr/lib/p401-r4', 'p401-log-stream', 'p401-w3-install-ok')))
            check('UI startup does not require the unavailable awk applet',
                  not re.search(r'(^|[;|&\s])awk(?:\s|$)', '\n'.join(
                      line for line in text.splitlines() if not line.lstrip().startswith('#'))))
            check('production startup never enables laboratory naming',
                  not re.search(r'P401_UI_LAB\s*=\s*[\"\']?1', text))
            check('compatibility manifest is pinned by dedicated launcher',
                  f'{zlib.crc32(compatibility.read_bytes()):08x} {compatibility.stat().st_size}' in text)
            rows = compatibility.read_text().splitlines()
            check('compatibility manifest pins installed UI library',
                  any(line.endswith(' /' + UI_PREFIX + '/libp401-ui.so') for line in rows))
            if a.variant == 'rc2':
                parsed = [row.split(' ', 2) for row in rows]
                expected_paths = VENDOR_ABI_PATHS | {'/' + UI_PREFIX + '/libp401-ui.so',
                                                    '/usr/libexec/carplay-revival/verify'} | {
                                                        '/' + path for path in RC2_EXTRA_ABI_PINS}
                check('RC2 compatibility manifest pins UI, ten vendor ABI files and static verifier',
                      len(parsed) == 12 and {row[2] for row in parsed} == expected_paths)
                check('RC2 connection provider compatibility row pins exact CRC and length',
                      all(f"{pin['crc32']} {pin['bytes']} /{path}" in rows
                          for path, pin in RC2_EXTRA_ABI_PINS.items()))
            for row in rows:
                crc, size, path = row.split(' ', 2)
                check('actual ARM verifier accepts ' + path,
                      path.startswith('/') and '..' not in Path(path).parts and
                      run(['qemu-arm', '-cpu', 'cortex-a7', str(helper), 'verify',
                           str(root / path.lstrip('/')), crc, size]).returncode == 0)
            check('actual ARM verifier rejects changed bytes',
                  run(['qemu-arm', '-cpu', 'cortex-a7', str(helper), 'verify',
                       str(library), '00000000', str(library.stat().st_size)]).returncode != 0)
        dhcp = root / 'usr/libexec/carplay-revival/udhcpd'
        r = run(['qemu-arm', '-cpu', 'cortex-a7', str(dhcp), '--help'])
        check('field-tested DHCP executable runs help under ARM emulation', r.returncode == 0)
        targets = [('native ARM loader resolves ' + name, root / 'usr/bin' / name)
                   for name in ('MsnFirstInit', 'MsnCoreApp', 'carplay', 'gocsdk', 'hostapd')]
        if a.variant != 'rc1':
            targets.append(('native ARM loader resolves Jaguar UI preload', root / UI_PREFIX / 'libp401-ui.so'))
        if a.variant == 'rc2':
            targets.extend(('native ARM loader resolves connection provider: ' + path, root / path)
                           for path in RC2_EXTRA_ABI_PINS)
        for label, executable in targets:
            paths = ':'.join(str(root / p) for p in ('usr/lib', 'lib', 'usr/local/Qt4.7.4/lib'))
            argv = ['qemu-arm', '-cpu', 'cortex-a7', '-L', str(root), '-E', 'LD_LIBRARY_PATH=' + paths,
                    str(root / 'lib/ld-linux-armhf.so.3'), '--list', str(executable)]
            r = run(argv)
            check(label, r.returncode == 0 and 'not found' not in r.stdout + r.stderr)
            if executable.name == 'carplay':
                check('native CarPlay selects the installed patched library', str(root / 'usr/lib/libAirPlay.so') in r.stdout)
        completed = True
    finally:
        result = {'passed': completed and bool(checks) and all(x['passed'] for x in checks), 'count': len(checks), 'checks': checks,
                  'variant': a.variant,
                  'scope': 'Actual ARM BusyBox/loader in fixtures; no kernel boot, MCU, radio or full CarPlay session.'}
        if ui_evidence is not None:
            result.update(library_sha256=expected_ui_sha, ui_native_evidence=ui_evidence,
                          owner_tested_ui_binary_unchanged=False, complete_image_vehicle_tested=False,
                          full_flash_recovery_proven=False)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
