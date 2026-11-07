"""Run the real ARM GUI in Docker's private network/PID/IPC and fake framebuffer.

No host namespace mounts, real devices or phone captures are used. Build and
historical packages stay separate; this script never constructs an installer.
"""
from pathlib import Path
import argparse, hashlib, json, os, shutil, struct, subprocess, sys, time, uuid, zipfile

UI=Path(__file__).resolve().parents[2]
REPO=UI.parents[1]
BUILD=UI/'build/cloud'
DOCKER=['env','-u','DOCKER_HOST','-u','DOCKER_CONTEXT','-u','DOCKER_TLS','-u','DOCKER_TLS_VERIFY','-u','DOCKER_CERT_PATH','docker','--host=unix:///var/run/docker.sock']
sys.path.insert(0,str(UI/'lab/reference'))
from capture_screen import png_from_bgra


def docker(*args,**kwargs):
    return subprocess.run(DOCKER+list(map(str,args)),check=True,**kwargs)


def prepare_image(archive):
    context=BUILD/'runtime-image';context.mkdir(parents=True,exist_ok=True)
    shutil.copy2(archive,context/'rootfs.tar')
    shutil.copy2(UI/'lab/reference/libp401-pc-fb.so',context/'libp401-pc-fb.so')
    with zipfile.ZipFile(UI/'packages/INSTALL.zip') as z:
        (context/'libp401-ui.so').write_bytes(z.read('msn_autocopy/data/carplay-revival/lib/libp401-ui.so'))
    name='p401-qemu-copy-'+uuid.uuid4().hex[:8]
    docker('create','--name',name,'carplay-dev:local',stdout=subprocess.DEVNULL)
    try:docker('cp',name+':/usr/bin/qemu-arm',context/'qemu-arm')
    finally:docker('rm',name,stdout=subprocess.DEVNULL)
    shutil.copy2(Path(__file__).with_name('Dockerfile.runtime'),context/'Dockerfile')
    docker('build','--network=none','-t','p401-native-runtime:local',context)


def build_probe(extra_sources=(),destination=None):
    # Reuse the exact ARM/Qt flags and linked vendor files from the candidate build.
    command=json.loads((UI/'build/BUILD.json').read_text())['command']
    command=[x.replace('-soname,libp401-ui.so','-soname,libp401-test-probe.so') for x in command if not x.endswith('.cpp')]
    command[-1]=str(destination or UI/'build/cloud/libp401-test-probe.so')
    command[1:1]=['-I'+str(UI/'src'),str(Path(__file__).with_name('probe.cpp')),str(Path(__file__).with_name('settings_probe.cpp'))]+list(map(str,extra_sources))
    subprocess.run(command,check=True)


class NativeSession:
    def __init__(self,label,profile,library,probe=True,lab=False,menu_case=None,saved_name=None,probe_library=None,saved_appearance=None,probe_timeout=5,probe_complete_marker=None):
        self.directory=BUILD/'runs'/label
        if self.directory.exists():shutil.rmtree(self.directory)
        self.directory.mkdir(parents=True)
        self.profile=profile
        self.library=Path(library).resolve()
        self.probe_enabled=probe
        self.lab=lab
        self.menu_case=menu_case
        self.saved_name=saved_name
        self.saved_appearance=saved_appearance
        self.probe_timeout=probe_timeout
        self.probe_complete_marker=probe_complete_marker
        self.probe_library=Path(probe_library).resolve() if probe_library else BUILD/'libp401-test-probe.so'
        self.name='p401-native-'+uuid.uuid4().hex[:10]
        self.processes=[]
        self.handles=[]
        self.frames=[]

    def start(self,wait_ready=True):
        r=self.directory
        if self.menu_case is not None:(r/'menu-case.txt').write_text(self.menu_case)
        (r/'input.bin').write_bytes(b'');(r/'frame.bgra').write_bytes(bytes(800*480*4))
        (r/'dbus.conf').write_text('<busconfig><type>session</type><listen>unix:path=/tmp/p401-bus</listen><auth>EXTERNAL</auth><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        data=r/'data';profile=data/'msncfg';profile.mkdir(parents=True)
        (data/'carplay-revival').mkdir()
        if self.saved_name is not None:(data/'carplay-revival/network-name').write_bytes(self.saved_name)
        if self.saved_appearance is not None:(data/'carplay-revival/appearance').write_bytes(self.saved_appearance)
        if self.profile is not None:(profile/'MsnProductInfo.ini').write_bytes(self.profile)
        (profile/'FactoryConfig.ini').write_text('[General]\n')
        for p in [r,*r.rglob('*')]:p.chmod(0o777 if p.is_dir() else 0o666)
        if self.library.stat().st_mode & 0o444 != 0o444:self.library.chmod(0o644)
        mounts=[f'type=bind,src={r},dst=/lab/control',f'type=bind,src={data},dst=/data',f'type=bind,src={r}/frame.bgra,dst=/dev/fb0',f'type=bind,src={self.library},dst=/lab/libp401-ui.so,readonly']
        if self.probe_enabled:
            probe=self.probe_library
            if probe.stat().st_mode & 0o444 != 0o444:probe.chmod(0o644)
            mounts.append(f'type=bind,src={probe},dst=/lab/libp401-test-probe.so,readonly')
        args=['run','-d','--name',self.name,'--network=none','--ipc=private','--cap-drop=ALL','--security-opt=no-new-privileges','--tmpfs','/tmp:rw,nosuid,nodev']
        for mount in mounts:args+=['--mount',mount]
        docker(*args,'p401-native-runtime:local',stdout=subprocess.DEVNULL)
        self.launch('dbus',['/qemu-arm','-E','LD_LIBRARY_PATH=/usr/lib:/lib','/usr/bin/dbus-daemon','--nofork','--config-file=/lab/control/dbus.conf'])
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            test=subprocess.run(DOCKER+['exec',self.name,'/qemu-arm','/bin/busybox','test','-S','/tmp/p401-bus'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if test.returncode==0:break
            time.sleep(.1)
        else:raise AssertionError('Private bus failed: '+(r/'dbus.log').read_text())
        env={'QTDIR':'/usr/local/Qt4.7.4','QT_PLUGIN_PATH':'/usr/local/Qt4.7.4/plugins','QT_QWS_FONTDIR':'/usr/local/Qt4.7.4/lib/fonts','QWS_DISPLAY':'LinuxFb:mmWidth154:mmHeight87:0','QWS_SIZE':'800x480','QWS_MOUSE_PROTO':'None','QWS_KEYBOARD':'None','LD_LIBRARY_PATH':'/usr/local/Qt4.7.4/lib:/usr/lib:/lib','QT_DEBUG_PLUGINS':'1','LD_PRELOAD':('/lab/libp401-test-probe.so:' if self.probe_enabled else '')+'/lab/libp401-ui.so:/lab/libp401-pc-fb.so','DBUS_SESSION_BUS_ADDRESS':'unix:path=/tmp/p401-bus','P401_UI_LAYOUT':'xfr'}
        if self.lab:env['P401_UI_LAB']='1'
        cmd=['/qemu-arm','-cpu','cortex-a7']
        for key,value in env.items():cmd+=['-E',key+'='+value]
        self.app=self.launch('native-ui',cmd+['/usr/bin/MsnCoreApp','-qws'])
        if wait_ready:self.wait(lambda:'native XFR menu attached' in self.log,20,capture_boot=True)
        time.sleep(.3)
        return self

    @property
    def log(self):return (self.directory/'native-ui.log').read_text(errors='replace')

    def launch(self,label,args):
        handle=(self.directory/(label+'.log')).open('wb');self.handles.append(handle)
        p=subprocess.Popen(DOCKER+['exec',self.name]+args,stdout=handle,stderr=subprocess.STDOUT)
        self.processes.append(p);return p

    def wait(self,fn,timeout=5,capture_boot=False):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if self.app.poll() is not None:raise AssertionError('ARM application exited: '+self.log[-4000:])
            if capture_boot:
                frame=(self.directory/'frame.bgra').read_bytes()
                if not self.frames or frame!=self.frames[-1]:self.frames.append(frame)
            if fn():return
            time.sleep(.025)
        raise AssertionError('Native GUI operation timed out: '+self.log[-2000:])

    def tap(self,x,y):
        with (self.directory/'input.bin').open('ab',buffering=0) as f:
            f.write(struct.pack('<iii',x,y,1));time.sleep(.08);f.write(struct.pack('<iii',x,y,0))
        time.sleep(.7)

    def probe(self,action=''):
        result=self.directory/'cloud-probe-results.txt';result.unlink(missing_ok=True)
        request=self.directory/'cloud-probe.request';request.write_text(action);request.chmod(0o666)
        self.wait(lambda:result.exists() and (not self.probe_complete_marker or self.probe_complete_marker in result.read_text()),self.probe_timeout)
        # close/final write can follow creation by a fraction of a frame.
        time.sleep(.05)
        return result.read_text()

    def capture(self,label):
        path=self.directory/(label+'.png')
        path.write_bytes(png_from_bgra((self.directory/'frame.bgra').read_bytes()))
        return str(path)

    def close(self):
        subprocess.run(DOCKER+['rm','-f',self.name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for p in self.processes:
            try:p.wait(timeout=3)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        for handle in self.handles:handle.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-image',type=Path)
    parser.add_argument('--build-probe',action='store_true')
    parser.add_argument('--build-rc2-probe',action='store_true')
    args=parser.parse_args()
    if args.prepare_image:prepare_image(args.prepare_image.resolve())
    if args.build_probe:build_probe()
    if args.build_rc2_probe:build_probe([Path(__file__).with_name('rc2_probe.cpp')],BUILD/'libp401-rc2-test-probe.so')
