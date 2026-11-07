"""Fresh menu/boot regressions of an exact ARM binary using isolated model fixtures.

The separate probe mutates only synthetic GUI models and observes native model
lookups. It does not emulate an MCU, radio, CarPlay session or physical boot.
"""
from pathlib import Path
import argparse, hashlib, json, time
from native import BUILD, UI, NativeSession

PROFILE=b'[General]\nMcuType=7\nBlueToothType=3\nWlanType=1\n'

def values(state):
    return dict(line.split('=',1) for line in state.splitlines() if '=' in line and not line.startswith(('widget=','app=')))

def visible(state,name):
    return any(line.startswith('widget=') and line.split(',')[1:3]==[name,'1'] for line in state.splitlines())

def wait_seconds(session,seconds,capture=False):
    deadline=time.monotonic()+seconds
    session.wait(lambda:time.monotonic()>=deadline,seconds+2,capture_boot=capture)

def run(library,only=None,save_report=True):
    library=Path(library).resolve();expected_hash=hashlib.sha256(library.read_bytes()).hexdigest()
    results=[]
    def record(case,session,**details):
        assert hashlib.sha256(library.read_bytes()).hexdigest()==expected_hash,'Library changed during native checks'
        results.append({'case':case,'passed':True,'sampled_boot_frames':len(session.frames),**details})
        print('PASS native menu',case,flush=True)
    if not only or 'footer' in only:
        s=NativeSession('menu-footer',PROFILE,library)
        try:
            s.start();state=s.probe('unknown-exit');assert 'app=31337, Exit ' in state,state
            wait_seconds(s,.8)
            footer=s.capture('unknown-exit-footer')
            # Return to the original vendor model before checking native
            # actions. The unknown-ID fixture establishes classification only;
            # it is not evidence that a synthetic ID is a supported vendor app.
            s.probe('model-restore');wait_seconds(s,.8)
            s.tap(200,410);wait_seconds(s,1)
            state=s.probe();assert '9' in values(state)['visible_apps'].split(','),state
            s.tap(44,30);wait_seconds(s,.6)
            s.tap(580,410);s.wait(lambda:'CarPlay name Settings page attached' in s.log)
            wait_seconds(s,.6);state=s.probe()
            assert '8' in values(state)['visible_apps'].split(','),state
            record('unknown-exit-classification-and-original-native-footer-actions',s,screenshot=footer,exit_native_app=9,settings_native_app=8)
        finally:s.close()
    if not only or 'lost' in only:
        s=NativeSession('menu-model-loss',PROFILE,library)
        try:
            s.start();wait_seconds(s,.8)
            before=values(s.probe());wait_seconds(s,1.4);after=values(s.probe())
            assert after['menu_paints']==before['menu_paints'],(before,after)
            assert after['source_shows']==before['source_shows'] and after['source_hides']==before['source_hides'],(before,after)
            record('static-menu-does-not-repaint',s,menu_paints=int(after['menu_paints']))
            for action in ['model-empty','model-missing','model-unknown-only','model-exit-only','model-main-only']:
                s.probe(action);wait_seconds(s,.8)
                state=s.probe();before=values(state)
                assert before['ready_marker']=='1' and before['source_hidden']=='0',state
                assert not visible(state,'RevivalNativeMenu'),state
                wait_seconds(s,1.3);after=values(s.probe())
                assert after['source_shows']==before['source_shows'] and after['source_hides']==before['source_hides'],(action,before,after)
                assert after['menu_paints']==before['menu_paints'],(action,before,after)
                s.probe('model-restore');wait_seconds(s,.8)
                state=s.probe();assert visible(state,'RevivalNativeMenu') and values(state)['source_hidden']=='1',state
                record(action+'-restores-stock-without-flicker',s)
        finally:s.close()
    if not only or 'delayed' in only:
        for mode in ['initial-empty','initial-missing']:
            s=NativeSession('menu-'+mode,PROFILE,library,menu_case=mode)
            try:
                s.start(wait_ready=False)
                s.wait(lambda:'initial model fixture' in s.log,5,capture_boot=True)
                wait_seconds(s,2,True);state=s.probe();data=values(state)
                assert data['ready_marker']=='0' and data['source_hidden']=='1',state
                assert visible(state,'RevivalNativeMenu'),state
                loading=s.capture('loading')
                s.probe('model-restore');s.wait(lambda:'native XFR menu attached' in s.log,5,capture_boot=True)
                state=s.probe();assert values(state)['ready_marker']=='1' and visible(state,'RevivalNativeMenu'),state
                record(mode+'-waits-for-model',s,loading_screenshot=loading,home_screenshot=s.capture('recovered-home'))
            finally:s.close()
    if not only or 'hidden' in only:
        s=NativeSession('menu-hidden-before-paint',PROFILE,library,menu_case='initial-hidden')
        try:
            s.start();state=s.probe();data=values(state)
            assert data['hidden_before_paint']=='1' and data['menu_paints']=='0' and data['ready_marker']=='1',state
            assert not visible(state,'RevivalNativeMenu'),state
            wait_seconds(s,1.3);state=s.probe();assert values(state)['menu_paints']=='0',state
            s.probe('launcher-show');wait_seconds(s,.8);state=s.probe()
            assert visible(state,'RevivalNativeMenu') and int(values(state)['menu_paints'])>0,state
            record('hidden-launcher-ready-without-forcing-home-visible',s,screenshot=s.capture('returned-home'))
        finally:s.close()
    if not only or 'timeout' in only:
        s=NativeSession('menu-invalid-timeout',PROFILE,library,menu_case='initial-unknown-only')
        try:
            s.start(wait_ready=False);s.wait(lambda:'initial model fixture' in s.log,5,capture_boot=True)
            state=s.probe();assert values(state)['ready_marker']=='0',state
            began=time.monotonic()
            s.wait(lambda:'launcher model unavailable; showing original interface' in s.log,66,capture_boot=True)
            state=s.probe();data=values(state)
            assert data['ready_marker']=='0' and data['source_hidden']=='0' and not visible(state,'RevivalNativeMenu'),state
            record('invalid-model-timeout-fails-open',s,seconds_waited=round(time.monotonic()-began,2),screenshot=s.capture('stock-fallback'))
        finally:s.close()
    report={'library_sha256':expected_hash,'passed':True,'cases':results,'scope':'Actual ARM Qt GUI in private Docker namespaces and fake framebuffer, production P401_UI_LAB unset. Separate test-only model fixtures cover delayed/empty/missing/unrecognized/lost models, original native Exit row lookup, stable repaint behavior and hidden-before-first-paint readiness. The hidden fixture represents an off-screen launcher; it does not activate or emulate real automatic CarPlay. Boot frames are sampled, not proof of physical boot display timing or sub-frame tearing. Shell watchdog/package delivery checks are separate.','historical_evidence_modified':False}
    if save_report:
        target=BUILD/'MENU_CLOUD_CHECKS.json';target.write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,default=UI/'build/libp401-ui.so');p.add_argument('--only',nargs='*',choices=['footer','lost','delayed','hidden','timeout']);args=p.parse_args();run(args.library,args.only)
