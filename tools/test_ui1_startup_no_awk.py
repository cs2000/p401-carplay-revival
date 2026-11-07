"""Check UI1 startup without awk, using disposable process fixtures.

Use --arm-root for the matching ARM BusyBox shell under QEMU. No vendor service
is loaded; native Qt Settings eligibility is tested separately in the GUI lab.
"""
from pathlib import Path
import argparse
import os
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--arm-root', type=Path)
args = parser.parse_args()
arm_root = args.arm_root.resolve() if args.arm_root else None
shell = ['qemu-arm', '-L', str(arm_root), str(arm_root / 'bin/busybox'), 'sh'] if arm_root else ['sh']
source = (REPO / 'experimental/ui1/src/run-ui.sh.in').read_text()
build = REPO / 'build'
build.mkdir(exist_ok=True)
profiles = [('type3', b'[General]\nBlueToothType=3\n'), ('other-type', b'[General]\nBlueToothType=5\n'), ('missing-profile', None)]

with tempfile.TemporaryDirectory(prefix='ui1-startup-no-awk-', dir=build) as temporary:
    fixture = Path(temporary)
    area = fixture / 'data/carplay-revival'
    tmp = fixture / 'tmp'
    bin_dir = fixture / 'bin'
    profile = fixture / 'MsnProductInfo.ini'
    for directory in (area, tmp, bin_dir):
        directory.mkdir(parents=True)
    helper = fixture / 'helper'
    helper.write_text('#!/bin/sh\nexit 0\n')
    helper.chmod(0o755)
    # Deliberately reject awk; the production wrapper must not require it.
    awk = bin_dir / 'awk'
    awk.write_text('#!/bin/sh\necho called > "$UI1_GATE_FIXTURE/awk-called"\nexit 127\n')
    awk.chmod(0o755)
    gui = bin_dir / 'MsnCoreApp'
    gui.write_text('#!/bin/sh\nprintf "STARTED:%s:%s:%s\\n" "$P401_UI_LAYOUT" "${P401_UI_NAMES-unset}" "${P401_UI_NAMES_REASON-unset}"\nprintf "ready\\n" > "$UI1_GATE_FIXTURE/tmp/p401-ui-ready"\n')
    gui.chmod(0o755)
    script = source.replace('/data/carplay-revival', str(area)).replace('/usr/lib/p401-r4/p401-diag', str(helper))
    script = script.replace('/msnprofile/MsnProductInfo.ini', str(profile)).replace('/tmp/p401-', str(tmp / 'p401-'))
    # Record the launch without loading an ARM Qt library into a host fixture.
    script = script.replace('LD_PRELOAD=', 'P401_GATE_TEST_PRELOAD=')
    runner = fixture / 'run-ui.sh'
    runner.write_text(script)
    subprocess.run(shell + ['-n', str(runner)], check=True)
    (area / 'compatibility.txt').write_text('')
    (area / 'state').write_text('enabled\n')
    (tmp / 'p401-w3-install-ok').write_text('verified\n')
    env = dict(os.environ, PATH=str(bin_dir) + ':' + os.environ['PATH'], UI1_GATE_FIXTURE=str(fixture), P401_UI_NAMES='1', P401_UI_NAMES_REASON='stale-flag')
    env.pop('P401_UI_LAB', None)
    for name, content in profiles:
        profile.unlink(missing_ok=True)
        if content is not None:
            profile.write_bytes(content)
        run = subprocess.run(shell + [str(runner)], env=env, capture_output=True, timeout=10)
        assert run.returncode == 0, (name, run.stderr.decode())
        assert 'STARTED:xfr:unset:unset' in run.stdout.decode().splitlines(), (name, run.stdout.decode(), run.stderr.decode())
        assert not (fixture / 'awk-called').exists(), 'startup invoked the unavailable awk dependency'
        assert (profile.read_bytes() if profile.exists() else None) == content, name + ': factory profile changed'
        assert (area / 'state').read_text() == 'enabled\n', name + ': UI unexpectedly disabled'
        print('PASS', name, '(no awk, stale flags cleared, profile unchanged)')
print(f'{len(profiles)} startup cases passed ({"ARM BusyBox/QEMU" if arm_root else "host shell"}); native Qt eligibility is a separate test.')
