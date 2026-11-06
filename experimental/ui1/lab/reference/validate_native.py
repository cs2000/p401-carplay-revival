"""Drive the actual isolated ARM GUI, and check the native naming endpoints."""
from pathlib import Path
import subprocess, time, struct, json, hashlib, sys

WS=Path(__file__).resolve().parents[2]
R=WS/'work/ui_customization/tests/runtime'
E=WS/'work/ui_customization/tests/evidence';E.mkdir(exist_ok=True)
sys.path.insert(0,str(WS/'work/visual_emulator'))
from capture_screen import png_from_bgra
script='/opt/p401-workspace/work/visual_emulator/boot_probe.py'
cmd=['wsl','-d','Codex-P401-Build','-u','root','--','unshare','-m','-n','-p','-i','-f','python3',script,'--test-ui','--native-layout','--live']

def wait_for(fn,timeout=25):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if fn():return
        time.sleep(.15)
    raise AssertionError('Native lab check timed out')

def tap(x,y):
    with (R/'input.bin').open('ab',buffering=0) as f:
        f.write(struct.pack('<iii',x,y,1));time.sleep(.08);f.write(struct.pack('<iii',x,y,0))
    time.sleep(.65)

def probe():
    (R/'probe-results.txt').unlink(missing_ok=True);(R/'probe.request').touch()
    wait_for(lambda:(R/'probe-results.txt').exists() and 'native_restart_lock=' in (R/'probe-results.txt').read_text(),5)
    s=(R/'probe-results.txt').read_text()
    return s,dict(line.split('=',1) for line in s.splitlines() if '=' in line and not line.startswith('app='))

def capture(name):
    for _ in range(30):
        try:
            frame=(R/'frame.bgra').read_bytes()
            if len(frame)==800*480*4:break
        except PermissionError:pass
        time.sleep(.05)
    else:raise AssertionError('No complete framebuffer frame')
    (E/(name+'.png')).write_bytes(png_from_bgra(frame))

all_results=[]
tested_hash=hashlib.sha256((WS/'work/ui_customization/build/libp401-ui.so').read_bytes()).hexdigest()
for case,content,expected in [('default',None,None),('invalid',b'bad\nname\n',None),('maximum',b'ABCDEFGHIJKLMNOPQRSTUVWX\n','ABCDEFGHIJKLMNOPQRSTUVWX'),('jaguar',b'Jaguar XFR\n','Jaguar XFR')]:
    (R/'input.bin').write_bytes(b'');(R/'probe.request').unlink(missing_ok=True)
    (R/'network-name').unlink(missing_ok=True)
    if content is not None:(R/'network-name').write_bytes(content)
    (R/'native-ui.log').write_bytes(b'')
    with (E/(case+'-launcher.log')).open('w') as log:
        p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            wait_for(lambda:'native XFR menu attached' in (R/'native-ui.log').read_text(errors='replace'))
            assert json.loads((R/'status.json').read_text())['ui_binary_sha256']==tested_hash,'Wrong library loaded in simulator'
            time.sleep(.5);capture(case+'-home');tap(640,150)
            s,d=probe();(E/(case+'-native.txt')).write_text(s)
            assert d['child_preload']=='unset' and d['name_validation']=='PASS',d
            assert d['other_key']=='6' and d['unrelated_ssid']=='Unrelated network',d
            assert d['native_restart_lock']=='available',d
            assert 'bluetooth_desired' in d,d
            if expected:
                for k in ['saved_name','hostapd_ssid','advertised_ssid','bluetooth_desired']:assert d[k]==expected,(case,k,d)
            else:
                assert d['saved_name']=='' and d['hostapd_ssid']=='carplay_test' and d['advertised_ssid']=='carplay_test',d
                assert d['bluetooth_desired'] not in ('Jaguar XFR','ABCDEFGHIJKLMNOPQRSTUVWX'),d
            capture(case+'-bluetooth')
            routes=[]
            if case=='jaguar':
                for label,x,y,app in [('CarPlay',140,150,4),('Android Auto',390,150,13),('Bluetooth',640,150,3),('Music',140,285,2),('Video',390,285,7),('Mirroring',640,285,11),('Exit',200,410,9),('Settings',580,410,8)]:
                    tap(44,30);tap(x,y);_,state=probe()
                    routes.append({'label':label,'expected':app,'visible':[int(x) for x in state['visible_apps'].split(',') if x]})
                    capture('route-'+label.replace(' ','-'))
                # Video opens the vendor's message window (ID 10) when this
                # hardware-free lab has no USB media. Confirm its real plugin
                # was loaded before accepting that native error screen.
                logtext=(R/'native-ui.log').read_text(errors='replace')
                for r in routes:
                    r['passed']=r['expected'] in r['visible'] or (r['expected']==7 and r['visible']==[10] and 'Load App Plugin 7 "/usr/lib/libVideoPlayer.so"' in logtext)
                assert all(r['passed'] for r in routes),routes
                tap(90,143);capture('native-name-settings')
            all_results.append({'case':case,'native':d,'routes':routes,'passed':True})
            print(case,'PASS',d.get('bluetooth_desired'),flush=True)
        finally:
            (R/'stop').touch()
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5)

assert hashlib.sha256((WS/'work/ui_customization/build/libp401-ui.so').read_bytes()).hexdigest()==tested_hash,'Build changed during checks'
result={'library_sha256':tested_hash,'cases':all_results,'hardware_radio_tested':False,'passed':True}
(E/'NATIVE_CHECKS.json').write_text(json.dumps(result,indent=2)+'\n')
print('All native checks passed.',flush=True)
