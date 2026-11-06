"""Run a bounded native UI probe in a private filesystem/network/PID namespace."""
from pathlib import Path
import os, subprocess, shutil, json, resource, time, sys, hashlib

ws = Path('/opt/p401-workspace')
work = ws / 'work/visual_emulator'
base = Path('/opt/p401-build/candidate-r1/root')
root = Path('/opt/p401-visual-lab/root')
live = '--live' in sys.argv
runtime = work / 'runtime'
designs = '--designs' in sys.argv
settings_preview = '--settings-preview' in sys.argv
if designs or settings_preview:
    root = Path('/opt/p401-ui-preview/root')
    runtime = ws / 'work/ui_customization/runtime'
if '--test-ui' in sys.argv:
    root = Path('/opt/p401-ui-test/root')
    runtime = ws / 'work/ui_customization/tests/runtime'
    settings_preview = True
runtime.mkdir(parents=True, exist_ok=True)
if not live:
    (runtime / 'input.bin').write_bytes(b'')
assert os.readlink('/proc/self/ns/net') != os.readlink('/proc/1/ns/net') or os.getpid() == 1
assert json.loads(subprocess.check_output(['ip', '-j', 'link']))[0]['ifname'] == 'lo'
assert len(json.loads(subprocess.check_output(['ip', '-j', 'link']))) == 1
subprocess.run(['mount', '--make-rprivate', '/'], check=True)
if not root.exists():
    shutil.copytree(base, root, symlinks=True)
    print('Independent visual-lab filesystem copied.', flush=True)
for part in ('proc', 'dev', 'sys', 'tmp', 'var/run', 'lab'):
    (root / part).mkdir(parents=True, exist_ok=True)
(root / 'lab/control').mkdir(exist_ok=True)
subprocess.run(['mount', '--bind', str(runtime), str(root / 'lab/control')], check=True)
subprocess.run(['mount', '-t', 'proc', '-o', 'ro,nosuid,nodev,noexec', 'proc', str(root / 'proc')], check=True)
for part in ('dev', 'sys', 'tmp', 'var/run'):
    subprocess.run(['mount', '-t', 'tmpfs', 'tmpfs', str(root / part)], check=True)
for name in ('null', 'zero', 'urandom', 'random'):
    (root / 'dev' / name).touch()
    subprocess.run(['mount', '--bind', '/dev/' + name, str(root / 'dev' / name)], check=True)
for part in ('dev/shm', 'dev/input', 'tmp/runtime-root'):
    (root / part).mkdir(parents=True, exist_ok=True)
shutil.copy2('/usr/bin/qemu-arm', root / 'qemu-arm')
shutil.copy2('/lib/ld-musl-x86_64.so.1', root / 'lib/ld-musl-x86_64.so.1')
shutil.copy2(work / 'libp401-pc-fb.so', root / 'lab/libp401-pc-fb.so')
if designs or settings_preview:
    shutil.copy2(ws / 'work/ui_customization/build/libp401-ui.so', root / 'lab/libp401-ui.so')
with (root / 'dev/fb0').open('wb') as fb:
    fb.truncate(800 * 480 * 4)
(root / 'var/run/lib/dbus').mkdir(parents=True, exist_ok=True)
(root / 'var/run/lib/dbus/machine-id').write_text('40140140140140140140140140140140\n')
(root / 'lab/dbus.conf').write_text('''<busconfig><type>session</type>
<listen>unix:path=/tmp/p401-bus</listen><auth>EXTERNAL</auth>
<policy context="default"><allow send_destination="*"/><allow receive_sender="*"/>
<allow own="*"/></policy></busconfig>''')
env = {'PATH': '/bin:/sbin:/usr/bin:/usr/sbin', 'HOME': '/tmp', 'USER': 'root',
       'QTDIR': '/usr/local/Qt4.7.4', 'QT_PLUGIN_PATH': '/usr/local/Qt4.7.4/plugins',
       'QT_QWS_FONTDIR': '/usr/local/Qt4.7.4/lib/fonts', 'QWS_DISPLAY': os.environ.get('LAB_DISPLAY', 'LinuxFb:mmWidth154:mmHeight87:0'),
       'QWS_SIZE': '800x480', 'QWS_MOUSE_PROTO': 'None', 'QWS_KEYBOARD': 'None',
       'LD_LIBRARY_PATH': '/usr/local/Qt4.7.4/lib:/usr/lib:/lib', 'QT_DEBUG_PLUGINS': '1',
       'LD_PRELOAD': '/lab/libp401-pc-fb.so',
       'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/tmp/p401-bus'}
if designs or settings_preview:
    env['LD_PRELOAD'] = '/lab/libp401-ui.so:' + env['LD_PRELOAD']
    env['P401_UI_LAB'] = '1'
    if designs:
        env['P401_UI_DEMO'] = '1'
    if '--native-layout' in sys.argv:
        env['P401_UI_LAYOUT'] = 'xfr'
bus_log = (work / 'dbus.log').open('wb')
bus = subprocess.Popen(['chroot', str(root), '/qemu-arm', '-cpu', 'cortex-a7', '-E',
                        'LD_LIBRARY_PATH=/usr/lib:/lib', '/usr/bin/dbus-daemon',
                        '--nofork', '--config-file=/lab/dbus.conf'], stdout=bus_log, stderr=subprocess.STDOUT)
for _ in range(50):
    if (root / 'tmp/p401-bus').exists() or bus.poll() is not None: break
    time.sleep(.1)
assert bus.poll() is None and (root / 'tmp/p401-bus').exists(), (work / 'dbus.log').read_text()
cmd = ['chroot', str(root), '/qemu-arm', '-cpu', 'cortex-a7']
if not live:
    cmd += ['-strace']
for k, v in env.items():
    cmd += ['-E', k + '=' + v]
cmd += ['/usr/bin/MsnCoreApp', '-qws']
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
try:
    if live:
        (runtime / 'stop').unlink(missing_ok=True)
        log = (runtime / 'native-ui.log').open('wb')
        app = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        (runtime / 'status.json').write_text(json.dumps({'running': True, 'native_binary': 'MsnCoreApp', 'hardware_emulated': False,'ui_binary_sha256':hashlib.sha256((root/'lab/libp401-ui.so').read_bytes()).hexdigest() if designs or settings_preview else None}))
        deadline = time.monotonic() + 14400
        try:
            while app.poll() is None and time.monotonic() < deadline and not (runtime / 'stop').exists():
                frame = (root / 'dev/fb0').read_bytes()
                temp = runtime / 'frame.tmp'
                temp.write_bytes(frame)
                try:
                    temp.replace(runtime / 'frame.bgra')
                except PermissionError:
                    pass # Windows viewer may briefly hold the previous frame.
                time.sleep(.15)
        finally:
            if app.poll() is None:
                app.kill()
            app.wait(timeout=5)
            log.close()
            (runtime / 'status.json').write_text(json.dumps({'running': False, 'exit_code': app.returncode}))
    else:
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
            output, code = r.stdout, r.returncode
        except subprocess.TimeoutExpired as exc:
            output, code = exc.stdout or b'', 'timeout'
        probe_output = runtime if designs or settings_preview else work
        (probe_output / 'boot-probe.log').write_bytes(output[:2000000])
        shutil.copyfile(root / 'dev/fb0', probe_output / 'framebuffer.bgra')
        print('UI probe result:', code)
        print(output.decode(errors='replace')[-3000:])
finally:
    bus.terminate()
    bus.wait(timeout=3)
    bus_log.close()
