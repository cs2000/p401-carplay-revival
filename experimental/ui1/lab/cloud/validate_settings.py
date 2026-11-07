"""Production-mode Settings and native naming checks on an exact ARM library.

The separate observer never sets P401_UI_LAB. Save & restart is driven with real
pointer events. Vendor reboot dispatch is observed and forwarded in a private
container with no reboot capability or hardware; physical reboot is not tested.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,time
from native import BUILD,UI,DOCKER,NativeSession

TYPE3=b'[General]\nMcuType=7\nBlueToothType=3\nWlanType=1\n'
PROFILES=[
 ('type3',TYPE3,True),
 ('busy-restart-lock',TYPE3,True),
 ('whitespace-crlf',b'[General]\r\nMcuType=7\r\n \tBlueToothType \t= \t3 \t\r\nWlanType=1\r\n',True),
 ('general-case',b'[general]\nMcuType=7\nBlueToothType=3\n',True),
 ('quoted-type',b'[General]\nMcuType=7\nBlueToothType="3"\n',True),
 ('lowercase-key',b'[General]\nMcuType=7\nbluetoothtype=3\n',False),
 ('unsupported',b'[General]\nMcuType=7\nBlueToothType=5\n',False),
 ('invalid-type',b'[General]\nMcuType=7\nBlueToothType=unknown\n',False),
 ('missing-key',b'[General]\nMcuType=7\n',False),
 ('missing-file',None,False),
]

def values(state):
 return dict(line.split('=',1) for line in state.splitlines() if '=' in line and not line.startswith(('widget=','app=')))

def widget(state,name=None,kind=None):
 for line in state.splitlines():
  if not line.startswith('widget='):continue
  fields=line[7:].split(',')
  if len(fields)!=7 or fields[2]!='1':continue
  if name is not None and fields[1]!=name:continue
  if kind is not None and fields[0]!=kind:continue
  return tuple(map(int,fields[3:]))
 return None

def wait_widget(session,name=None,kind=None,present=True):
 found=[None]
 def check():
  found[0]=widget(session.probe(),name,kind)
  return bool(found[0])==present
 session.wait(check,10)
 return found[0]

def read_saved(session):
 return subprocess.check_output(DOCKER+['exec',session.name,'/qemu-arm','/bin/busybox','cat','/data/carplay-revival/network-name'])

def unchanged_profile(session,profile):
 product=session.directory/'data/msncfg/MsnProductInfo.ini'
 assert (product.read_bytes() if product.exists() else None)==profile,'Factory product profile changed'
 assert (session.directory/'data/msncfg/FactoryConfig.ini').read_bytes()==b'[General]\n','Factory configuration changed'

def name_panel(session):
 # QEMU's pointer shim consumes one record per select call. Under parallel
 # startup load a press/release can lag; check the native window and retry only
 # while still on Home, rather than mistaking a pressed tile for navigation.
 for attempt in range(4):
  session.tap(580,410);time.sleep(.4)
  if widget(session.probe(),kind='SettingWindow'):break
 else:raise AssertionError('Settings footer did not activate the native window')
 session.tap(90,143)
 bounds=wait_widget(session,name='RevivalNamePanel')
 return bounds

def open_bluetooth(session):
 # Use the original native model and the same grid ordering as the actual menu.
 state=session.probe();apps=[]
 kinds={4:0,13:1,3:2,2:3,7:4,11:5,9:6,8:7}
 for line in state.splitlines():
  if line.startswith('app='):
   ident=int(line[4:].split(',',1)[0]);kind=kinds.get(ident,8)
   if kind not in (6,7):apps.append((kind,ident))
 apps.sort(key=lambda app:app[0])
 index=next(i for i,app in enumerate(apps) if app[1]==3)
 rows=3 if len(apps)>8 else 2;cols=max(1,(len(apps)+rows-1)//rows);cell=762//cols;height=278//rows
 session.tap(24+(index%cols)*cell+cell//2,86+(index//cols)*height+height//2)
 session.wait(lambda:'bluetooth_desired=' in session.probe(),10)
 return values(session.probe())

def validate(library,only=None):
 digest=hashlib.sha256(library.read_bytes()).hexdigest();results=[]
 for label,profile,available in PROFILES:
  if only and label not in only:continue
  s=NativeSession('settings-'+label,profile,library,saved_name=b'OLD\n' if label=='busy-restart-lock' else None)
  try:
   s.start();s.wait(lambda:'MSNCoreApp exec' in s.log,15);time.sleep(.4);state=values(s.probe())
   assert state['laboratory']=='0' and state['names_available']==str(int(available)),state
   assert state['child_preload']=='unset',state
   bounds=name_panel(s);panel=s.capture('name-panel')
   x,y,width,height=bounds;s.tap(x+width//2,y+217)
   wait_widget(s,name='RevivalNameEditor',present=available)
   editor=s.capture('name-editor' if available else 'disabled-panel')
   observed_restart=False
   if available and label=='busy-restart-lock':
    for _ in range(3):s.tap(690,373)
    for x,y in [(321,319),(696,268),(659,217),(509,217),(246,268)]:s.tap(x,y)
    s.tap(660,440)
    lock=s.directory/'force-reboot-lock';lock.write_text('busy');lock.chmod(0o666)
    assert values(s.probe())['native_restart_lock']=='1'
    s.tap(600,423);time.sleep(.5)
    assert read_saved(s)==b'OLD\n','Busy restart overwrote the saved name'
    assert not (s.directory/'native-restart.requested').exists(),'Busy restart dispatched reboot'
    assert not list((s.directory/'data/carplay-revival').glob('network-name.*'))
    s.capture('busy-restart-preserved-name');lock.unlink()
   elif available and label=='type3':
    blocked=values(s.probe('save:bad@name'))
    assert blocked['save_result']=='0' and not (s.directory/'data/carplay-revival/network-name').exists(),blocked
    # Type CLOUD using the real native keyboard and commit the real confirmation.
    for x,y in [(321,319),(696,268),(659,217),(509,217),(246,268)]:s.tap(x,y)
    s.tap(660,440);confirmation=s.capture('save-confirmation')
    assert values(s.probe())['native_restart_lock']=='0','Native restart lock unexpectedly busy'
    s.tap(600,423)
    s.wait(lambda:(s.directory/'data/carplay-revival/network-name').exists(),10)
    assert read_saved(s)==b'CLOUD\n'
    mode=subprocess.check_output(DOCKER+['exec',s.name,'/qemu-arm','/bin/busybox','stat','-c','%a','/data/carplay-revival/network-name']).strip()
    assert mode==b'600',mode
    s.wait(lambda:(s.directory/'native-restart.requested').exists(),12)
    observed_restart=True
    assert not list((s.directory/'data/carplay-revival').glob('network-name.*')),'Temporary save file left behind'
   elif available:
    s.tap(100,440);wait_widget(s,name='RevivalNameEditor',present=False)
   else:
    blocked=values(s.probe('save:BLOCKED'))
    assert blocked['save_result']=='0' and not (s.directory/'data/carplay-revival/network-name').exists(),blocked
   unchanged_profile(s,profile)
   results.append({'case':label,'passed':True,'production_mode':True,'names_available':available,'name_panel':panel,'editor':editor,'real_editor_commit':observed_restart,'native_restart_dispatched':observed_restart})
   print('PASS production Settings',label,flush=True)
  finally:s.close()
 # A fresh process must apply the saved name together at all three native endpoints.
 for label,content,expected in [('reload-saved',b'CLOUD\n','CLOUD'),('maximum-name',b'ABCDEFGHIJKLMNOPQRSTUVWX\n','ABCDEFGHIJKLMNOPQRSTUVWX'),('invalid-saved-file',b'bad\nname\n',None)]:
  if only and label not in only:continue
  s=NativeSession('settings-'+label,TYPE3,library,saved_name=content)
  try:
   s.start();s.wait(lambda:'MSNCoreApp exec' in s.log,15);time.sleep(.4);state=open_bluetooth(s)
   assert state['laboratory']=='0' and state['names_available']=='1',state
   assert state['saved_name']==(expected or ''),state
   for endpoint in ('hostapd_ssid','advertised_ssid','bluetooth_desired'):
    if expected:assert state[endpoint]==expected,(endpoint,state)
    else:assert state[endpoint] not in ('CLOUD','bad','bad\nname'),(endpoint,state)
   assert state['other_key']=='6' and state['unrelated_ssid']=='Unrelated network' and state['child_preload']=='unset',state
   unchanged_profile(s,TYPE3)
   results.append({'case':label,'passed':True,'production_mode':True,'endpoints':{key:state[key] for key in ('saved_name','hostapd_ssid','advertised_ssid','bluetooth_desired','other_key','unrelated_ssid','child_preload')}})
   print('PASS production reload',label,flush=True)
  finally:s.close()
 assert hashlib.sha256(library.read_bytes()).hexdigest()==digest,'Candidate binary changed during checks'
 report={'library_sha256':digest,'passed':True,'cases':results,'scope':'Exact ARM GUI with real Settings/editor pointer events, native save/atomic rename/private file permissions and forwarded vendor reboot request; fresh production-mode process naming endpoint checks. Separate test observer, synthetic private profiles, fake framebuffer, private network/PID/IPC container with no reboot capability or device access. No radio, MCU, iPhone, physical reboot, vehicle or flash success established. Historical evidence unchanged.'}
 destination=BUILD/'SETTINGS_CLOUD_CHECKS.json'
 if only and destination.exists():
  previous=json.loads(destination.read_text())
  if previous.get('library_sha256')==digest:
   combined={case['case']:case for case in previous.get('cases',[]) if case.get('passed')}
   combined.update({case['case']:case for case in results});report['cases']=list(combined.values())
 expected={case[0] for case in PROFILES}|{'reload-saved','maximum-name','invalid-saved-file'}
 report['expected_case_count']=len(expected)
 report['complete']=expected<={case['case'] for case in report['cases']}
 report['passed']=report['complete'] and all(case['passed'] for case in report['cases'])
 destination.write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,default=UI/'build/libp401-ui.so');p.add_argument('--only',nargs='*');a=p.parse_args();validate(a.library.resolve(),a.only)
