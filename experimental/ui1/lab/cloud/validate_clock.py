"""Verify the exact native clock, artwork and header restoration without changing time."""
from pathlib import Path
import argparse,datetime,hashlib,json,time
from native import BUILD,UI,NativeSession


def widget_visible(state,name):
    return any(x.startswith('widget=') and x.split(',')[1:3]==[name,'1'] for x in state.splitlines())


def validate(library):
    digest=hashlib.sha256(library.read_bytes()).hexdigest()
    s=NativeSession('final-clock-glass',b'[General]\nMcuType=7\nBlueToothType=3\nWlanType=1\n',library,probe=True,lab=False)
    try:
        s.start();state=s.probe('english-fixture');assert 'laboratory=0\n' in state
        time.sleep(.6)
        before=(s.directory/'frame.bgra').read_bytes();first=s.capture('home-clock-glass')
        start=datetime.datetime.now().strftime('%H:%M');print('Native clock:',start,flush=True)
        end=time.monotonic()+62
        while datetime.datetime.now().strftime('%H:%M')==start and time.monotonic()<end:time.sleep(.2)
        time.sleep(1.5)
        after=(s.directory/'frame.bgra').read_bytes();second=s.capture('home-clock-next-minute');now=datetime.datetime.now().strftime('%H:%M')
        def roi(b):return b''.join(b[(y*800+86)*4:(y*800+220)*4] for y in range(59))
        assert roi(before)!=roi(after) and now!=start,'Clock did not advance visually'
        assert 'REVIVAL: static glass artwork loaded 768x512' in s.log
        s.tap(580,410)
        end=time.monotonic()+8
        while time.monotonic()<end:
            state=s.probe()
            if widget_visible(state,'SettingWindow'):break
            time.sleep(.1)
        assert widget_visible(state,'SettingWindow'),'Settings screen did not open'
        assert not widget_visible(state,'RevivalHomeBrand'),'Clock obscures Settings title'
        header=s.capture('settings-native-title')
        s.tap(44,30);time.sleep(.5);state=s.probe()
        assert widget_visible(state,'RevivalHomeBrand'),'Clock did not return on Home'
        returned=s.capture('home-returned')
        assert hashlib.sha256(library.read_bytes()).hexdigest()==digest,'Candidate changed during native test'
        report={'library_sha256':digest,'passed':True,'clock_start':start,'clock_end':now,'clock_pixels_changed':True,'artwork_decoded':'768x512','setting_window_visible':True,'clock_overlay_hidden_in_settings':True,'home_screenshots':[first,second,returned],'settings_header':header,'scope':'Exact ARM candidate, production mode LAB unset, private synthetic profile and English source-model fixture. Natural Qt clock minute advance; host time unchanged.'}
        (BUILD/'CLOCK_CLOUD_CHECKS.json').write_text(json.dumps(report,indent=2)+'\n')
        print('PASS native clock, artwork and header restoration',digest)
        return report
    finally:s.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,default=UI/'build/libp401-ui.so');a=p.parse_args();validate(a.library.resolve())
