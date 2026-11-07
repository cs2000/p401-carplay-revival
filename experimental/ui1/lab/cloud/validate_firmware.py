"""Exercise the unchanged full-image UI runner with the real ARM GUI in isolation.

The image input must be the roundtrip tar extracted from the candidate UBI image.
A separate image verifier checks the complete production inventory before this
lab changes its disposable runtime copy. Static host dispatchers only bridge
QEMU child execs, retaining the original ARM BusyBox/verifier and GUI binaries.
No kernel, device services, radios, MCU or physical reboot are emulated.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import time
import uuid

from native import BUILD, UI, DOCKER, NativeSession, docker
from validate_settings import (TYPE3, values, name_panel, open_bluetooth,
                               unchanged_profile)

UI_PATH = 'usr/libexec/carplay-revival/ui/libp401-ui.so'
RUNNER_PATH = 'usr/libexec/carplay-revival/ui/run-ui.sh'
MANIFEST_PATH = 'usr/libexec/carplay-revival/ui/compatibility.txt'
VERIFIER_PATH = 'usr/libexec/carplay-revival/verify'
UI_SHA256 = 'c62c2d49d3ce423d9cf11d96325e7ee5e50d7967ce0a865b2cf6f3a6f6593639'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root_tar, expected_ui=UI_SHA256, probe_library=None):
    digest = sha(root_tar)
    context = BUILD / 'firmware-runtime' / digest[:16]
    context.mkdir(parents=True, exist_ok=True)
    # Read only documented regular files from the archive; never extract paths.
    with tarfile.open(root_tar) as tf:
        members = {x.name.removeprefix('./'): x for x in tf.getmembers()}
        for source, target in [('bin/busybox', 'busybox.arm'),
                               (VERIFIER_PATH, 'verify.arm'),
                               (UI_PATH, 'libp401-ui.so'),
                               (RUNNER_PATH, 'production-run-ui.sh'),
                               (MANIFEST_PATH, 'production-compatibility.txt')]:
            item = members[source]
            assert item.isfile(), 'Expected regular image file: ' + source
            (context / target).write_bytes(tf.extractfile(item).read())
    assert sha(context / 'libp401-ui.so') == expected_ui, 'Image UI does not match the expected exact binary'
    shutil.copy2(root_tar, context / 'rootfs.tar')
    shutil.copy2(UI / 'lab/reference/libp401-pc-fb.so', context / 'libp401-pc-fb.so')
    shutil.copy2(probe_library or BUILD / 'libp401-test-probe.so', context / 'libp401-test-probe.so')
    subprocess.run(['cc', '-static', '-O2', '-Wall', '-Wextra',
                    str(Path(__file__).with_name('firmware_dispatch.c')),
                    '-o', str(context / 'dispatch')], check=True)
    temporary = 'p401-qemu-copy-' + uuid.uuid4().hex[:8]
    docker('create', '--name', temporary, 'carplay-dev:local', stdout=subprocess.DEVNULL)
    try:
        docker('cp', temporary + ':/usr/bin/qemu-arm', context / 'qemu-arm')
    finally:
        docker('rm', temporary, stdout=subprocess.DEVNULL)
    for path in context.iterdir():
        if path.is_file():
            path.chmod(0o755 if path.name in ('dispatch', 'qemu-arm', 'busybox.arm', 'verify.arm') else 0o644)
    (context / 'Dockerfile').write_text('''FROM scratch
ADD rootfs.tar /
COPY qemu-arm /qemu-arm
COPY busybox.arm /lab/busybox.arm
COPY verify.arm /lab/verify.arm
COPY libp401-pc-fb.so /lab/libp401-pc-fb.so
COPY libp401-test-probe.so /lab/libp401-test-probe.so
COPY dispatch /bin/busybox
COPY dispatch /usr/libexec/carplay-revival/verify
COPY dispatch /lab/dispatch
COPY dispatch /lab/bin/MsnCoreApp
ENTRYPOINT ["/qemu-arm", "/lab/busybox.arm", "sleep", "3600"]
''')
    image = 'p401-firmware-native:' + digest[:16]
    docker('build', '--network=none', '-t', image, context)
    return context, image


class FirmwareSession(NativeSession):
    def __init__(self, label, context, image, profile=TYPE3, saved_name=None,
                 state=None, manifest=None, dispatch_case=None, appearance=None):
        # Each run retains its private-mode synthetic files without chmod or
        # deleting another run's evidence.
        super().__init__('firmware-' + label + '-' + uuid.uuid4().hex[:8],
                         profile, context / 'libp401-ui.so',
                         saved_name=saved_name)
        self.image = image
        self.state = state
        self.manifest = manifest
        self.dispatch_case = dispatch_case
        self.appearance = appearance

    def start(self, wait_ready=True):
        r = self.directory
        (r / 'input.bin').write_bytes(b'')
        (r / 'frame.bgra').write_bytes(bytes(800 * 480 * 4))
        (r / 'dbus.conf').write_text('<busconfig><type>session</type><listen>unix:path=/tmp/p401-bus</listen><auth>EXTERNAL</auth><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        data = r / 'data'
        profile = data / 'msncfg'
        profile.mkdir(parents=True)
        area = data / 'carplay-revival'
        if self.saved_name is not None or self.state is not None or self.appearance is not None:
            area.mkdir()
        if self.profile is not None:
            (profile / 'MsnProductInfo.ini').write_bytes(self.profile)
        (profile / 'FactoryConfig.ini').write_text('[General]\n')
        if self.saved_name is not None:
            (area / 'network-name').write_bytes(self.saved_name)
        if self.state is not None:
            (area / 'state').write_bytes(self.state)
        if self.appearance is not None:
            (area / 'appearance').write_bytes(self.appearance)
        if self.dispatch_case:
            (r / 'dispatch-case.txt').write_text(self.dispatch_case)
        if self.manifest is not None:
            (r / 'manifest.txt').write_bytes(self.manifest)
        for path in [r, *r.rglob('*')]:
            path.chmod(0o777 if path.is_dir() else 0o666)
        mounts = [f'type=bind,src={r},dst=/lab/control',
                  f'type=bind,src={data},dst=/data',
                  f'type=bind,src={r}/frame.bgra,dst=/dev/fb0']
        if self.manifest is not None:
            mounts.append(f'type=bind,src={r}/manifest.txt,dst=/{MANIFEST_PATH},readonly')
        args = ['run', '-d', '--name', self.name, '--network=none', '--ipc=private',
                '--cap-drop=ALL', '--security-opt=no-new-privileges',
                '--tmpfs', '/tmp:rw,nosuid,nodev']
        for mount in mounts:
            args += ['--mount', mount]
        docker(*args, self.image, stdout=subprocess.DEVNULL)
        self.launch('dbus', ['/qemu-arm', '-E', 'LD_LIBRARY_PATH=/usr/lib:/lib',
                            '/usr/bin/dbus-daemon', '--nofork',
                            '--config-file=/lab/control/dbus.conf'])
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = subprocess.run(DOCKER + ['exec', self.name, '/lab/dispatch',
                                             'test', '-S', '/tmp/p401-bus'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode == 0:
                break
            time.sleep(.1)
        else:
            raise AssertionError('Private D-Bus failed: ' + (r / 'dbus.log').read_text())
        env = {'PATH': '/lab/bin:/usr/bin:/bin', 'QTDIR': '/usr/local/Qt4.7.4',
               'QT_PLUGIN_PATH': '/usr/local/Qt4.7.4/plugins',
               'QT_QWS_FONTDIR': '/usr/local/Qt4.7.4/lib/fonts',
               'QWS_DISPLAY': 'LinuxFb:mmWidth154:mmHeight87:0', 'QWS_SIZE': '800x480',
               'QWS_MOUSE_PROTO': 'None', 'QWS_KEYBOARD': 'None',
               'LD_LIBRARY_PATH': '/usr/local/Qt4.7.4/lib:/usr/lib:/lib',
               'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/tmp/p401-bus',
               # The exact production runner must clear these obsolete/bypass flags.
               'P401_UI_NAMES': 'stale', 'P401_UI_NAMES_REASON': 'stale',
               'P401_UI_LAB': '1'}
        # Pass variables through Docker rather than starting any host service.
        command = ['exec']
        for key, value in env.items():
            command += ['-e', key + '=' + value]
        command += [self.name, '/lab/dispatch', 'sh', '/' + RUNNER_PATH]
        handle = (r / 'native-ui.log').open('wb')
        self.handles.append(handle)
        self.app = subprocess.Popen(DOCKER + command, stdout=handle, stderr=subprocess.STDOUT)
        self.processes.append(self.app)
        if wait_ready:
            self.wait(lambda: 'native XFR menu attached' in self.log, 25, capture_boot=True)
            time.sleep(.4)
        return self

    def probe(self, action=''):
        # A complete widget dump can exceed one stdio buffer. Wait for the
        # observer's final field rather than only file creation.
        result = self.directory / 'cloud-probe-results.txt'
        result.unlink(missing_ok=True)
        request = self.directory / 'cloud-probe.request'
        request.write_text(action)
        request.chmod(0o666)
        self.wait(lambda: result.exists() and 'native_restart_lock=' in
                  result.read_text(errors='replace'), 8)
        return result.read_text()


def verify_fallback(context, image, label, **kwargs):
    session = FirmwareSession(label, context, image, **kwargs)
    try:
        session.start(wait_ready=False)
        began = time.monotonic()
        session.wait(lambda: 'LAB_DISPATCH: stock real ARM MsnCoreApp' in session.log,
                     70 if kwargs.get('dispatch_case') == 'timeout' else 15)
        session.wait(lambda: 'MSNCoreApp exec' in session.log, 20)
        custom = 'LAB_DISPATCH: custom real ARM MsnCoreApp' in session.log
        assert custom == bool(kwargs.get('dispatch_case')), session.log
        assert 'native XFR menu attached' not in session.log
        if kwargs.get('dispatch_case'):
            state = subprocess.check_output(DOCKER + ['exec', session.name, '/lab/dispatch',
                                                       'cat', '/data/carplay-revival/state'])
            assert state == b'disabled\n'
        unchanged_profile(session, TYPE3)
        return {'case': label, 'passed': True, 'stock_gui_executed': True,
                'actual_gui_crash_injected': False,
                'adapter_process_failure_fixture': kwargs.get('dispatch_case'),
                'seconds_until_stock': round(time.monotonic() - began, 3)}
    finally:
        session.close()


def validate(root_tar, output, only=None, variant='rc1', ui_evidence=None, probe_library=None):
    # Fail before launching native cases if this output location is unwritable.
    # A failed or interrupted rerun must not leave an earlier green report.
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'passed': False, 'complete': False,
                                  'state': 'preparing', 'variant': variant}) + '\n')
    expected_ui = UI_SHA256
    if variant == 'rc2':
        evidence = json.loads(ui_evidence.read_text())
        assert evidence.get('passed') is True and evidence.get('complete') is True, 'RC2 native evidence incomplete'
        expected_ui = evidence['library_sha256']
        assert len(expected_ui) == 64 and expected_ui != UI_SHA256, 'RC2 needs its new native-validated binary'
        assert evidence.get('cases') and all(case.get('passed') is True for case in evidence['cases']), 'RC2 native cases incomplete'
        from validate_rc2_regressions import rc2_name_panel
        navigate_name_panel = rc2_name_panel
    else:
        navigate_name_panel = name_panel
    context, image = prepare(root_tar, expected_ui, probe_library)
    cases = []
    report = {'passed': False, 'root_tar_sha256': sha(root_tar),
              'library_sha256': expected_ui, 'runner_sha256': sha(context / 'production-run-ui.sh'),
              'production_runner_bytes_unchanged': True, 'full_profile_executed': False,
              'cases': cases, 'hardware_boot_tested': False,
              'hardware_radio_tested': False, 'hardware_reboot_tested': False,
              'full_flash_recovery_proven': False,
              'scope': 'Fresh actual ARM BusyBox shell, CRC verifier and MsnCoreApp from the candidate roundtrip root tar. Exact production runner, manifest and UI library; disposable runtime replaces BusyBox/verifier entry points with static host dispatchers that invoke their preserved real ARM originals via QEMU. Verifier self-pin alone reads the preserved byte-identical /lab/verify.arm because its entry point is adapted; all other CRC targets retain production paths. MsnCoreApp PATH adapter adds only the fake framebuffer and test observer, without changing the ABI-pinned vendor GUI file. Private Docker network/PID/IPC, no capabilities/devices. Synthetic factory profiles and saved names; no kernel boot, radio, MCU, iPhone, physical reboot or flash test.'}
    if variant == 'rc2':
        report.update(variant=variant, ui_native_evidence_sha256=sha(ui_evidence),
                      observer_sha256=sha(context / 'libp401-test-probe.so'),
                      owner_tested_ui_binary_unchanged=False)
    try:
        if not only or 'healthy' in only:
            s = FirmwareSession('healthy', context, image)
            try:
                s.start()
                s.wait(lambda: 'MSNCoreApp exec' in s.log, 15)
                state = values(s.probe())
                assert state['laboratory'] == '0' and state['names_available'] == '1', state
                assert state['child_preload'] == 'unset', state
                assert not (s.directory / 'data/p401-w3').exists()
                assert not (s.directory / 'data/carplay-revival/state').exists()
                assert 'static glass artwork loaded 768x512' in s.log
                # Exercise both retained native footer actions before the editor.
                # The fake-pointer queue may need its first click to establish
                # focus. Retry only while the original Home app remains visible.
                for attempt in range(4):
                    s.tap(200, 410)
                    time.sleep(.5)
                    visible = values(s.probe()).get('visible_apps', '').split(',')
                    if '9' in visible:
                        break
                    assert '10' in visible, visible
                else:
                    raise AssertionError('Exit footer did not activate native app 9')
                for attempt in range(4):
                    s.tap(44, 30)
                    time.sleep(.4)
                    if '10' in values(s.probe()).get('visible_apps', '').split(','):
                        break
                else:
                    raise AssertionError('Native Home button did not restore launcher')
                x, y, width, height = navigate_name_panel(s)
                s.tap(x + width // 2, y + 217)
                s.wait(lambda: 'RevivalNameEditor' in s.probe(), 8)
                for x, y in [(321,319),(696,268),(659,217),(509,217),(246,268)]:
                    s.tap(x, y)
                s.tap(660,440)
                assert values(s.probe())['native_restart_lock'] == '0'
                s.tap(600,423)
                s.wait(lambda: (s.directory / 'data/carplay-revival/network-name').exists(), 10)
                saved = subprocess.check_output(DOCKER + ['exec', s.name, '/lab/dispatch',
                                                          'cat', '/data/carplay-revival/network-name'])
                assert saved == b'CLOUD\n'
                assert (s.directory / 'data/carplay-revival/network-name').stat().st_mode & 0o777 == 0o600
                s.wait(lambda: (s.directory / 'native-restart.requested').exists(), 12)
                assert not list((s.directory / 'data/carplay-revival').glob('network-name.*'))
                unchanged_profile(s, TYPE3)
                assert len((s.directory / 'verify-calls.txt').read_text().splitlines()) >= 12
                cases.append({'case': 'healthy', 'passed': True, 'no_field_w3_required': True,
                              'native_exit_action': 9, 'native_settings_action': 8,
                              'real_pointer_name_save': 'CLOUD', 'name_file_mode': '0600',
                              'native_restart_dispatched': True, 'factory_profile_unchanged': True,
                              'sampled_boot_frames': len(s.frames)})
                print('PASS full-image runner healthy native UI/save/restart request', flush=True)
            finally:
                s.close()
        if not only or 'reload' in only:
            appearance = b'P401-APPEARANCE-1\naccent=1\norder=0,1,2,3,4,5\npictures=0,1,2,3,4,5\n' if variant == 'rc2' else None
            s = FirmwareSession('reload', context, image, saved_name=b'CLOUD\n',
                                state=b'enabled\n' if variant == 'rc2' else None,
                                appearance=appearance)
            try:
                s.start()
                s.wait(lambda: 'MSNCoreApp exec' in s.log, 15)
                state = open_bluetooth(s)
                assert state['laboratory'] == '0' and state['names_available'] == '1', state
                for endpoint in ('hostapd_ssid', 'advertised_ssid', 'bluetooth_desired'):
                    assert state[endpoint] == 'CLOUD', (endpoint, state)
                assert state['other_key'] == '6' and state['unrelated_ssid'] == 'Unrelated network'
                assert state['child_preload'] == 'unset'
                unchanged_profile(s, TYPE3)
                if variant == 'rc2':
                    assert (s.directory / 'data/carplay-revival/state').read_bytes() == b'enabled\n'
                    assert (s.directory / 'data/carplay-revival/appearance').read_bytes() == appearance
                cases.append({'case': 'reload', 'passed': True,
                              'existing_userdata_ui_state_and_appearance_preserved': variant == 'rc2',
                              'endpoints': {key: state[key] for key in ('hostapd_ssid', 'advertised_ssid', 'bluetooth_desired')}})
                print('PASS full-image runner saved-name native endpoints', flush=True)
            finally:
                s.close()
        for label, options in [('disabled', {'state': b'disabled\n'}),
                               ('corrupt-manifest', {'manifest': b'corrupt\n'}),
                               ('crash', {'dispatch_case': 'crash'}),
                               ('timeout', {'dispatch_case': 'timeout'})]:
            if not only or label in only:
                cases.append(verify_fallback(context, image, label, **options))
                print('PASS full-image unchanged runner fallback', label, flush=True)
        expected = {'healthy', 'reload', 'disabled', 'corrupt-manifest', 'crash', 'timeout'}
        report['expected_case_count'] = len(expected)
        report['complete'] = expected <= {case['case'] for case in cases}
        report['passed'] = report['complete'] and all(case['passed'] for case in cases)
        return report
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root-tar', type=Path, required=True)
    p.add_argument('--output', type=Path, default=BUILD / 'FIRMWARE_NATIVE_CHECKS.json')
    p.add_argument('--only', nargs='*', help='Run selected fixtures; report remains incomplete')
    p.add_argument('--variant', choices=('rc1', 'rc2'), default='rc1')
    p.add_argument('--ui-evidence', type=Path, help='Required for RC2: complete passed exact-binary native report')
    p.add_argument('--probe-library', type=Path, help='Explicit separate plain test observer')
    a = p.parse_args()
    if (a.variant == 'rc2') != (a.ui_evidence is not None):
        p.error('--variant rc2 requires --ui-evidence; RC1 does not accept it')
    result = validate(a.root_tar.resolve(), a.output.resolve(), a.only, a.variant,
                      a.ui_evidence.resolve() if a.ui_evidence else None,
                      a.probe_library.resolve() if a.probe_library else None)
    print(json.dumps({'passed': result['passed'], 'complete': result.get('complete', False),
                      'output': str(a.output)}, indent=2))
