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

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--variant', choices=('rc1', 'jaguar'), default='rc1',
                    help='Keep clean RC1 checks by default; Jaguar also checks its dedicated UI launcher')
    a = ap.parse_args()
    root = a.root.resolve()
    qemu = ['/usr/bin/qemu-arm', '-cpu', 'cortex-a7', '-L', str(root), str(root / 'bin/busybox')]
    checks = []
    completed = False
    def check(label, ok):
        checks.append({'check': label, 'passed': bool(ok)})
        if not ok:
            raise AssertionError(label)
    def run(argv, **kw):
        return subprocess.run(argv, capture_output=True, text=True, timeout=30, **kw)
    def digest(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()
    try:
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
            check('Jaguar uses the exact owner-tested ARM UI library', digest(library) == UI_SHA)
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
        if a.variant == 'jaguar':
            targets.append(('native ARM loader resolves Jaguar UI preload', root / UI_PREFIX / 'libp401-ui.so'))
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
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
