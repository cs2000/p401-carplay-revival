"""Fresh RC2 features on the exact ARM GUI, isolated from radios and hardware.

Native link events are controlled input fixtures, not live phone connections.
All appearance changes and Advanced entry use Qt's real pointer input path.
"""
from pathlib import Path
import argparse, hashlib, json, subprocess, time
from native import BUILD, UI, DOCKER, NativeSession
from validate_settings import TYPE3, values, widget, wait_widget, unchanged_profile

OUT=BUILD/'rc2'
PROBE=BUILD/'libp401-rc2-test-probe.so'
DEFAULT=b'P401-APPEARANCE-1\naccent=0\norder=0,1,2,3,4,5\npictures=0,1,2,3,4,5\n'
CUSTOM=b'P401-APPEARANCE-1\naccent=1\norder=2,0,1,3,4,5\npictures=5,1,2,3,4,5\n'

def lines(state,prefix):
    return [line[len(prefix):].split('|') for line in state.splitlines() if line.startswith(prefix)]

def tap_rect(session,rect):
    x,y,w,h=map(int,rect.split(','));session.tap(x+w//2,y+h//2)

def tap_text_object(session,name):
    entries=[row for row in lines(session.probe(),'rc2_text=') if row[1]==name]
    assert len(entries)==1,(name,entries)
    tap_rect(session,entries[0][3])

def open_settings(session):
    for attempt in range(4):
        if widget(session.probe(),kind='SettingWindow'):return
        assert widget(session.probe(),name='RevivalNativeMenu'),'Cannot retry Settings outside Home'
        session.tap(580,410);time.sleep(.3)
    wait_widget(session,kind='SettingWindow')

def select_settings(session,label):
    open_settings(session)
    rows=[row for row in lines(session.probe(),'rc2_list=') if row[0]=='setItemListView' and label(row[2])]
    assert len(rows)==1,rows
    tap_rect(session,rows[0][3])

def open_appearance(session):
    select_settings(session,lambda text:text=='Appearance')
    x,y,w,h=wait_widget(session,name='RevivalAppearancePanel')
    session.tap(x+w//2,y+225)
    wait_widget(session,name='RevivalAppearanceEditor')

def prefs(state):
    result={}
    for line in state.splitlines():
        if line.startswith('rc2_tile='):
            kind,rank,picture=map(int,line[9:].split(','));result[kind]=(rank,picture)
    return result

def read_appearance(session):
    return subprocess.check_output(DOCKER+['exec',session.name,'/qemu-arm','/bin/busybox','cat','/data/carplay-revival/appearance'])

def session(label,library,appearance=None,saved_name=None):
    s=NativeSession('rc2-'+label,TYPE3,library,probe_library=PROBE,saved_appearance=appearance,saved_name=saved_name,probe_timeout=15,probe_complete_marker='rc2_probe_complete=1\n')
    try:s.start();s.wait(lambda:'MSNCoreApp exec' in s.log,20);time.sleep(.8)
    except BaseException:s.close();raise
    return s

def validate(library,only=None):
    OUT.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(library.read_bytes()).hexdigest();probe_digest=hashlib.sha256(PROBE.read_bytes()).hexdigest();results=[]
    destination=OUT/'RC2_FEATURE_CHECKS.json';previous_cases=[]
    if only and destination.exists():
        old=json.loads(destination.read_text())
        if old.get('library_sha256')==digest:
            previous_cases=[x for x in old.get('cases',[]) if x.get('passed') and x.get('case') not in only]
    # A failed/interrupted rerun must never leave a previous complete report
    # available to the package gate for this same candidate hash.
    destination.write_text(json.dumps(dict(library_sha256=digest,complete=False,passed=False,state='running',cases=previous_cases),indent=2)+'\n')
    selected=lambda name:not only or name in only
    def passed(name,**details):
        results.append(dict(case=name,passed=True,**details))
        destination.write_text(json.dumps(dict(library_sha256=digest,complete=False,passed=False,state='running',cases=previous_cases+results),indent=2)+'\n')
        print('PASS RC2',name,flush=True)
    if selected('connection-native-events'):
        s=session('connection',library)
        try:
            initial=values(s.probe());assert initial['laboratory']=='0'
            assert initial['rc2_connection_symbols']=='1' and initial['rc2_connected']=='0',initial
            s.probe('english-fixture');time.sleep(.8);home=s.capture('HOME-ENGLISH-FIXTURE');s.probe('model-restore')
            bluetooth=values(s.probe('bluetooth-ready-tags'))
            assert bluetooth['rc2_bluetooth_ready_tags_dispatched']=='1' and bluetooth['rc2_connected']=='0',bluetooth
            steps=[]
            # Physical transport/starting signals are insufficient; background
            # preserves a session; other transports do not destroy the active one.
            fixtures=[(0,1,False),(7,3,False),(2,4,False),(7,4,True),(7,6,True),
                      (0,10,True),(2,5,True),(7,8,False),(0,4,True),(0,39,True),
                      (0,5,False),(7,4,True),(7,2,False),(0,4,True),(0,3,False)]
            for kind,status,expected in fixtures:
                state=values(s.probe('link:%d:%d'%(kind,status)))
                assert state['rc2_native_link_dispatched']=='1',state
                assert state['rc2_connected']==str(int(expected)),(kind,status,state)
                assert state['rc2_status']==('Connected' if expected else 'Waiting for phone'),state
                steps.append(dict(type=kind,status=status,connected=expected))
            s.probe('launcher-show');time.sleep(.8)
            waiting=s.capture('WAITING')
            s.probe('link:7:4');s.probe('launcher-show');time.sleep(.8)
            connected=s.capture('CONNECTED')
            unchanged_profile(s,TYPE3)
            passed('connection-native-events',native_status_handler=True,bluetooth_ready_tags_insufficient=True,steps=steps,default_english_fixture_preview=home,waiting_preview=waiting,connected_preview=connected)
        finally:s.close()
    if selected('appearance-pointer-save'):
        s=session('appearance-save',library,saved_name=b'KEEP NAME\n')
        try:
            state=values(s.probe());assert state['rc2_preferences_symbols']=='1'
            assert prefs(s.probe())=={i:(i,i) for i in range(6)}
            assert not (s.directory/'data/carplay-revival/appearance').exists()
            open_appearance(s);accent_preview=s.capture('APPEARANCE-ACCENTS')
            s.tap(400,195) # Sapphire
            s.tap(400,101);pictures_preview=s.capture('APPEARANCE-PICTURES')
            s.tap(140,160);s.tap(700,330) # CarPlay picture index 5
            s.tap(656,101);order_preview=s.capture('APPEARANCE-ORDER')
            s.tap(200,241);s.tap(630,232);s.tap(630,232) # Bluetooth first
            s.tap(660,440);wait_widget(s,name='RevivalAppearanceEditor',present=False)
            path=s.directory/'data/carplay-revival/appearance'
            s.wait(path.exists);saved=read_appearance(s);assert saved==CUSTOM,saved
            assert path.stat().st_mode&0o777==0o600,oct(path.stat().st_mode)
            assert not list(path.parent.glob('appearance.*'))
            assert subprocess.check_output(DOCKER+['exec',s.name,'/qemu-arm','/bin/busybox','cat','/data/carplay-revival/network-name'])==b'KEEP NAME\n','Appearance save changed the existing network name'
            state=values(s.probe());assert state['rc2_accent']=='#75b4ef',state
            assert prefs(s.probe())=={0:(1,5),1:(2,1),2:(0,2),3:(3,3),4:(4,4),5:(5,5)}
            s.tap(45,30);wait_widget(s,name='RevivalNativeMenu');time.sleep(.8)
            personalised=s.capture('HOME-PERSONALISED')
            # Explicit synthetic English fixture is only for the public preview.
            # Restore the original model before any native-route assertion.
            s.probe('english-fixture');time.sleep(.8);english=s.capture('HOME-ENGLISH-FIXTURE');s.probe('model-restore')
            unchanged_profile(s,TYPE3)
            passed('appearance-pointer-save',private_atomic_file=True,existing_network_name_unchanged=True,accent_preview=accent_preview,pictures_preview=pictures_preview,order_preview=order_preview,home_preview=personalised,english_fixture_preview=english)
        finally:s.close()
    if selected('appearance-cancel'):
        s=session('appearance-cancel',library,appearance=CUSTOM)
        try:
            initial=s.probe();open_appearance(s)
            s.tap(400,308);s.tap(320,440);s.tap(100,440) # edit, defaults, cancel
            wait_widget(s,name='RevivalAppearanceEditor',present=False)
            assert (s.directory/'data/carplay-revival/appearance').read_bytes()==CUSTOM
            after=s.probe();assert prefs(after)==prefs(initial)
            assert values(after)['rc2_accent']==values(initial)['rc2_accent']
            unchanged_profile(s,TYPE3);passed('appearance-cancel',persisted_file_unchanged=True)
        finally:s.close()
    if selected('appearance-reload-native-routing'):
        s=session('appearance-reload',library,appearance=CUSTOM,saved_name=b'CLOUD\n')
        try:
            state=values(s.probe());assert state['rc2_accent']=='#75b4ef',state
            assert prefs(s.probe())[2][0]==0 and prefs(s.probe())[0]==(1,5)
            # First tile is now Bluetooth. This forwards the original row/model.
            for attempt in range(4):
                s.tap(145,145)
                if '3' in values(s.probe()).get('visible_apps','').split(','):break
                assert widget(s.probe(),name='RevivalNativeMenu'),'Unexpected non-Bluetooth route'
            state=values(s.probe());assert '3' in state['visible_apps'].split(','),state
            assert state['bluetooth_desired']=='CLOUD',state
            assert state['hostapd_ssid']=='CLOUD' and state['advertised_ssid']=='CLOUD'
            s.tap(45,30);wait_widget(s,name='RevivalNativeMenu');open_settings(s)
            themed=s.capture('SETTINGS-PERSONALISED')
            assert ['setItemListView','RevivalSettingsNavigation'] in lines(s.probe(),'rc2_delegate=')
            unchanged_profile(s,TYPE3)
            passed('appearance-reload-native-routing',bluetooth_original_row=True,name_endpoints_preserved=True,fixed_settings_footer=True,settings_preview=themed)
        finally:s.close()
    if selected('settings-native-advanced'):
        s=session('settings-advanced',library)
        try:
            # The native getter reads this runtime cache. Seed only the private
            # lab /tmp file so an empty hardware-free value cannot mask loss of
            # the native Advanced-page version label.
            subprocess.run(DOCKER+['exec',s.name,'/qemu-arm','/bin/busybox','sh','-c','printf "RC2-MCU-FIXTURE\\n" > /tmp/msn_mcu_version'],check=True)
            open_settings(s);state=s.probe()
            for label in ('CarPlay name','Appearance'):
                entries=[x for x in lines(state,'rc2_list=') if x[0]=='setItemListView' and x[2]==label]
                assert len(entries)==1,(label,entries)
                x,y,w,h=map(int,entries[0][3].split(','));assert 60<=y and y+h<=480,(label,entries)
            assert any(x[:2]==['SettingWindow','1'] for x in lines(state,'rc2_settings_theme=')),state
            assert ['setItemListView','RevivalSettingsNavigation'] in lines(state,'rc2_delegate=')
            settings=s.capture('SETTINGS')
            select_settings(s,lambda text:'显示' in text or 'Display' in text)
            wait_widget(s,kind='SetDisplayPanel');state=s.probe()
            assert any(x[:2]==['tabWidget','0,0'] for x in lines(state,'rc2_tabbar=')),state
            # The baseline native capability fixture hides this optional
            # backlight-page selector. Preserve its native hidden state rather
            # than requiring an image/button the native application suppresses.
            selectors=[line[7:].split(',') for line in state.splitlines() if line.startswith('widget=') and line[7:].split(',')[1]=='chkTabSel']
            assert len(selectors)==1 and selectors[0][:3]==['QPushButton','chkTabSel','0'],selectors
            display=s.capture('DISPLAY-NATIVE-CONTROLS')
            select_settings(s,lambda text:'系统信息' in text or 'System' in text)
            tap_text_object(s,'btnFactoryMode');wait_widget(s,kind='FactoryWindow')
            state=s.probe();assert ['tabFactory','1','3','tabFunction'] in lines(state,'rc2_tabs='),state
            assert any(x[:2]==['tabFactory','0,0'] for x in lines(state,'rc2_tabbar=')),state
            assert ['1','1','1'] in lines(state,'rc2_advanced_slot='),state
            factory=s.capture('FACTORY')
            for attempt in range(4):
                tap_text_object(s,'btnAdminSetting');time.sleep(.4);state=s.probe()
                if ['tabFactory','1','3','tabFunction'] not in lines(state,'rc2_tabs='):break
            assert ['tabFactory','2','3','tabAdminFunction'] in lines(state,'rc2_tabs='),state
            assert 'REVIVAL: native Advanced settings opened without PIN' in s.log
            assert not any(x[1]=='btnNum0' for x in lines(state,'rc2_text=')),state
            assert any(x[:2]==['1','1'] for x in lines(state,'rc2_mcu_version_label=')),state
            assert any('RC2-MCU-FIXTURE' in x[2] for x in lines(state,'rc2_mcu_version_label=')),state
            advanced=s.capture('ADVANCED-NO-PIN')
            unchanged_profile(s,TYPE3)
            passed('settings-native-advanced',real_pointer_native_slot=True,advanced_tab=2,native_mcu_version_label_preserved=True,synthetic_runtime_version_cache=True,factory_values_unchanged=True,native_optional_display_selector_hidden=True,settings_preview=settings,display_preview=display,factory_preview=factory,advanced_preview=advanced)
        finally:s.close()
    expected={'connection-native-events','appearance-pointer-save','appearance-cancel','appearance-reload-native-routing','settings-native-advanced'}
    if previous_cases:
        combined={x['case']:x for x in previous_cases};combined.update({x['case']:x for x in results});results=list(combined.values())
    complete=expected<={x['case'] for x in results}
    assert hashlib.sha256(library.read_bytes()).hexdigest()==digest,'Candidate changed during checks'
    assert hashlib.sha256(PROBE.read_bytes()).hexdigest()==probe_digest,'Observer changed during checks'
    report=dict(library_sha256=digest,observer_sha256=probe_digest,complete=complete,passed=complete and all(x['passed'] for x in results),expected_case_count=len(expected),cases=results,scope='Actual ARM native GUI in private Docker network/PID/IPC namespaces, fake framebuffer and real Qt pointer path. Link statuses are controlled native-handler fixtures, not live phone/radio sessions. No MCU, iPhone, physical restart, vehicle install, kernel boot or full-flash recovery proven. Historical RC1 artifacts/evidence unchanged.')
    destination.write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,default=UI/'build/libp401-ui.so');p.add_argument('--only',nargs='*');a=p.parse_args();validate(a.library.resolve(),a.only)
