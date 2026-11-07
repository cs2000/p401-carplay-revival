"""Exercise appearance persistence using the actual ARM production source/Qt.

Private, offline Docker fixtures cover corrupt input, strict permutation checks,
private atomic saves, restart reload and write failure. This does not claim a
physical touchscreen or storage endurance test. The probe is not shipped.
"""
from pathlib import Path
import argparse, contextlib, hashlib, json, shutil, subprocess, tempfile, uuid

UI=Path(__file__).resolve().parents[2]
REPO=UI.parents[1]
BUILD=UI/'build/cloud/preferences'
DOCKER=['env','-u','DOCKER_HOST','-u','DOCKER_CONTEXT','-u','DOCKER_TLS','-u','DOCKER_TLS_VERIFY','-u','DOCKER_CERT_PATH','docker','--host=unix:///var/run/docker.sock']
DEFAULT=b'P401-APPEARANCE-1\naccent=0\norder=0,1,2,3,4,5\npictures=0,1,2,3,4,5\n'
CUSTOM=b'P401-APPEARANCE-1\naccent=3\norder=5,4,3,2,1,0\npictures=2,3,4,5,0,1\n'
DEFAULT_TEXT='accent=0 order=0,1,2,3,4,5 pictures=0,1,2,3,4,5'
CUSTOM_TEXT='accent=3 order=5,4,3,2,1,0 pictures=2,3,4,5,0,1'
SESSION=None
CONTROL=None

def docker(*args,**kwargs):return subprocess.run(DOCKER+list(map(str,args)),check=True,**kwargs)

def source_identity():
    return {str(p.relative_to(UI)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [UI/'src/preferences.cpp',UI/'src/preferences.h',UI/'lab/cloud/preferences_probe.cpp']}

def build():
    BUILD.mkdir(parents=True,exist_ok=True)
    qtl='/repo/experimental/ui1/build/cloud/vendor-root/usr/local/Qt4.7.4/lib'
    command=['clang++','--target=arm-linux-gnueabihf','-march=armv7-a','-mfpu=vfpv3-d16','-mfloat-abi=hard',
             '-isystem','/usr/include/arm-linux-musleabihf','-I/repo/experimental/ui1/build/include',
             '-I/repo/experimental/ui1/build/include/QtCore','-I/repo/experimental/ui1/build/include/QtGui',
             '-I/repo/experimental/ui1/src','-fuse-ld=lld','-fPIC','-shared','-nostdlib','-nostdinc++',
             '-fno-exceptions','-fno-rtti','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
             '-std=c++11','-O2','-Wno-deprecated','-Wno-reserved-user-defined-literal',
             '/repo/experimental/ui1/src/preferences.cpp','/repo/experimental/ui1/lab/cloud/preferences_probe.cpp',
             qtl+'/libQtGui.so.4.7.4',qtl+'/libQtCore.so.4.7.4',
             '/repo/experimental/ui1/build/cloud/vendor-root/lib/libstdc++.so.6',
             '/repo/experimental/ui1/build/cloud/vendor-root/lib/libc.so.6',
             '-o','/repo/experimental/ui1/build/cloud/preferences/probe.so']
    docker('run','--rm','--network=none','--cap-drop=ALL','--security-opt=no-new-privileges','--user','1000:1000',
           '--mount',f'type=bind,src={REPO},dst=/repo','p401-ui-toolchain:local',*command)
    identity={'command':command,'sources':source_identity(),'probe_sha256':hashlib.sha256((BUILD/'probe.so').read_bytes()).hexdigest()}
    (BUILD/'BUILD.json').write_text(json.dumps(identity,indent=2)+'\n')
    return identity

def clear(directory):
    for p in directory.iterdir():
        if p.is_dir() and not p.is_symlink():shutil.rmtree(p)
        else:p.unlink()

@contextlib.contextmanager
def fixture_session(directory):
    # One private offline container keeps a large VFS toolchain image from
    # being copied for every input. Each probe is still a fresh ARM process.
    global SESSION,CONTROL
    CONTROL=directory;CONTROL.mkdir();SESSION='p401-preferences-'+uuid.uuid4().hex[:10]
    docker('run','-d','--rm','--name',SESSION,'--network=none','--ipc=private','--cap-drop=ALL','--security-opt=no-new-privileges','--user','1000:1000',
           '--mount',f'type=bind,src={REPO},dst=/repo,readonly',
           '--mount',f'type=bind,src={CONTROL},dst=/lab/control','p401-ui-toolchain:local','/bin/sleep','infinity',stdout=subprocess.DEVNULL)
    try:yield
    finally:
        subprocess.run(DOCKER+['rm','-f',SESSION],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        SESSION=None;CONTROL=None

def run(directory,action=None,readonly=False):
    if SESSION and not readonly:
        clear(CONTROL);shutil.copytree(directory,CONTROL,dirs_exist_ok=True,symlinks=True)
        args=['exec',SESSION]
    else:
        args=['run','--rm','--network=none','--ipc=private','--cap-drop=ALL','--security-opt=no-new-privileges','--user','1000:1000',
              '--mount',f'type=bind,src={REPO},dst=/repo,readonly',
              '--mount',f'type=bind,src={directory},dst=/lab/control'+(',readonly' if readonly else ''),'p401-ui-toolchain:local']
    args+=['/usr/bin/qemu-arm','-L','/repo/experimental/ui1/build/cloud/vendor-root',
          '-E','LD_LIBRARY_PATH=/repo/experimental/ui1/build/cloud/vendor-root/usr/local/Qt4.7.4/lib:/repo/experimental/ui1/build/cloud/vendor-root/usr/lib:/repo/experimental/ui1/build/cloud/vendor-root/lib',
          '-E','LD_PRELOAD=/repo/experimental/ui1/build/cloud/preferences/probe.so']
    if action:args+=['-E','P401_PREFERENCE_TEST_ACTION='+action]
    # This matching vendor BusyBox has no true applet. Its native shell supplies
    # an inert successful process after the test-only preload constructor runs.
    args+=['/repo/experimental/ui1/build/cloud/vendor-root/bin/busybox','sh','-c','exit 0']
    try:output=docker(*args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True).stdout
    except subprocess.CalledProcessError as error:raise RuntimeError(error.stdout) from error
    if SESSION and not readonly:
        clear(directory);shutil.copytree(CONTROL,directory,dirs_exist_ok=True,symlinks=True)
    return output

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--skip-build',action='store_true');args=parser.parse_args()
    (BUILD/'RESULT.json').unlink(missing_ok=True)
    if args.skip_build:
        identity=json.loads((BUILD/'BUILD.json').read_text())
        if identity['sources']!=source_identity() or identity['probe_sha256']!=hashlib.sha256((BUILD/'probe.so').read_bytes()).hexdigest():
            raise SystemExit('Preference probe is stale; run again without --skip-build.')
    else:identity=build()
    BUILD.mkdir(parents=True,exist_ok=True)
    checks=[]
    def check(name,passed):
        checks.append({'name':name,'passed':bool(passed)})
        if not passed:raise AssertionError(name)
    with tempfile.TemporaryDirectory(prefix='fixtures-',dir=BUILD) as tmp,fixture_session(Path(tmp)/'active'):
        root=Path(tmp)
        invalid={
            'missing':None,'empty':b'','truncated':DEFAULT[:-1],
            'duplicate-order':DEFAULT.replace(b'0,1,2,3,4,5\npictures',b'0,1,2,3,4,0\npictures'),
            'unknown-version':DEFAULT.replace(b'APPEARANCE-1',b'APPEARANCE-2'),
            'bad-accent':DEFAULT.replace(b'accent=0',b'accent=6'),
            'bad-picture':DEFAULT.replace(b'pictures=0',b'pictures=9'),
            'extra-key':DEFAULT+b'McuType=7\n','extra-byte':DEFAULT+b'\0',
            'noncanonical':DEFAULT.replace(b'accent=0',b'accent=00'),
            'oversized':DEFAULT+b'x'*256,
        }
        for label,data in invalid.items():
            directory=root/label;directory.mkdir()
            if data is not None:(directory/'appearance').write_bytes(data)
            output=run(directory)
            check(label+' defaults as a whole',DEFAULT_TEXT in output and 'revision=1 ranks=0,1,2,3,4,5' in output)
        directory=root/'symlink';directory.mkdir();(directory/'other').write_bytes(CUSTOM);(directory/'appearance').symlink_to('other')
        check('symlink input rejected',DEFAULT_TEXT in run(directory))
        directory=root/'roundtrip';directory.mkdir()
        (directory/'network-name').write_bytes(b'P401 name\n');(directory/'FactoryConfig.ini').write_bytes(b'[General]\nMCUType=7\n')
        output=run(directory,'custom')
        check('valid custom save applies',CUSTOM_TEXT in output and 'saved=1' in output and 'revision=2 ranks=5,4,3,2,1,0' in output)
        check('canonical exact bytes',(directory/'appearance').read_bytes()==CUSTOM)
        check('private saved mode',(directory/'appearance').stat().st_mode&0o777==0o600)
        check('no temporary files remain',sorted(p.name for p in directory.iterdir())==['FactoryConfig.ini','appearance','network-name'])
        check('name and factory fixture unchanged',(directory/'network-name').read_bytes()==b'P401 name\n' and (directory/'FactoryConfig.ini').read_bytes()==b'[General]\nMCUType=7\n')
        check('custom reload after restart',CUSTOM_TEXT in run(directory))
        for action in ['invalid-order','invalid-accent','invalid-picture']:
            output=run(directory,action)
            check(action+' save rejected','saved=0' in output and 'after '+CUSTOM_TEXT in output and 'revision=1' in output and (directory/'appearance').read_bytes()==CUSTOM)
        output=run(directory,'default',readonly=True)
        check('read-only save failure preserves current','saved=0' in output and 'after '+CUSTOM_TEXT in output and (directory/'appearance').read_bytes()==CUSTOM)
        output=run(directory,'default')
        check('restore defaults saves complete record','saved=1' in output and (directory/'appearance').read_bytes()==DEFAULT)
    report={'passed':all(c['passed'] for c in checks),'scope':'Actual ARM production preferences.cpp with vendor Qt in isolated offline QEMU fixtures; no physical storage/endurance claim.',
            'source_sha256':hashlib.sha256((UI/'src/preferences.cpp').read_bytes()).hexdigest(),
            'probe_sha256':identity['probe_sha256'],'build_command':identity['command'],'sources':identity['sources'],'checks':checks}
    (BUILD/'RESULT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(checks)} appearance storage checks passed; {BUILD/"RESULT.json"}')
if __name__=='__main__':main()
