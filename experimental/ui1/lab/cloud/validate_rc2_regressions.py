"""Run the existing naming, menu and clock checks on a separate RC2 candidate.

Example (from the repository root, with the documented offline toolchain/runtime):
  python experimental/ui1/lab/cloud/validate_rc2_regressions.py \\
    --library experimental/ui1/build/libp401-ui.so

The default output is build/cloud/rc2/regression under UI1. A fresh plain observer
is compiled from probe.cpp/settings_probe.cpp, excluding the RC2 feature helper.
The existing validators and their historical/default reports are unchanged.
Separate suites can be run with --suite settings, menu or clock; the aggregate
passes only when all 13 naming cases, all 11 menu cases and clock checks pass for
the same exact library and observer. No physical radio/reboot/flash is emulated.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, time

import native
import validate_settings
import validate_menu
import validate_clock

UI=native.UI
REPO=native.REPO
DEFAULT_OUTPUT=UI/'build/cloud/rc2/regression'
PROBE_NAME='libp401-test-probe.so'
REPORTS={'settings':'SETTINGS_CLOUD_CHECKS.json','menu':'MENU_CLOUD_CHECKS.json','clock':'CLOCK_CLOUD_CHECKS.json'}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def observer_sources():
    return {str(path.relative_to(UI)):digest(path)
            for path in [Path(__file__).with_name('probe.cpp'),Path(__file__).with_name('settings_probe.cpp')]}


def candidate_build(library):
    build=json.loads((UI/'build/BUILD.json').read_text())
    if build.get('sha256')!=digest(library):
        raise ValueError('The supplied library does not match the current exact BUILD.json; freeze/build the candidate first.')
    return build


def compile_probe(library,output):
    candidate_build(library)
    target=output/PROBE_NAME
    native.build_probe(destination=target)
    identity={'library_sha256':digest(library),'observer_sha256':digest(target),
              'sources':observer_sources(),'plain_observer':True,
              'build':json.loads((UI/'build/BUILD.json').read_text()),
              'scope':'Fresh separate probe.cpp/settings_probe.cpp observer; no RC2 helper and no production source linked into observer.'}
    (output/'PROBE.json').write_text(json.dumps(identity,indent=2)+'\n')


def docker_compile(library,output):
    # Reuse the documented pinned Qt/compiler/vendor flags inside the offline
    # toolchain. Both paths must be in the one authorized repository bind.
    library_inside=Path('/repo')/library.relative_to(REPO)
    output_inside=Path('/repo')/output.relative_to(REPO)
    native.docker('run','--rm','--network=none','--ipc=private','--cap-drop=ALL',
                  '--security-opt=no-new-privileges','--user','1000:1000',
                  '--mount',f'type=bind,src={REPO},dst=/repo',
                  'p401-ui-toolchain:local','python',
                  '/repo/experimental/ui1/lab/cloud/validate_rc2_regressions.py',
                  '--library',library_inside,'--output-dir',output_inside,'--compile-probe-only')


def check_probe(library,output):
    identity=json.loads((output/'PROBE.json').read_text())
    if identity.get('library_sha256')!=digest(library) or identity.get('observer_sha256')!=digest(output/PROBE_NAME):
        raise ValueError('Plain observer identity does not match this candidate.')
    if identity.get('sources')!=observer_sources() or identity.get('plain_observer') is not True:
        raise ValueError('Plain observer sources changed; rerun without --reuse-probe.')
    return identity


def rc2_name_panel(session):
    # Native attachItem sorts its row keys. Appearance is now before CarPlay
    # name, so the earlier UI1 test's fixed row-1 tap opens the wrong page.
    # Observe the matching native row and click its actual visible rectangle.
    for attempt in range(4):
        session.tap(580,410);time.sleep(.4)
        if validate_settings.widget(session.probe(),kind='SettingWindow'):break
    else:raise AssertionError('Settings footer did not activate the native window')
    state=session.probe();matches=[]
    for line in state.splitlines():
        if not line.startswith('settings_nav='):continue
        fields=line[len('settings_nav='):].split('|')
        if len(fields)!=4 or fields[2]!='CarPlay name':continue
        x,y,width,height=map(int,fields[3].split(','))
        if width>0 and height>0 and 0<=x+width//2<800 and 62<=y+height//2<480:
            matches.append((x,y,width,height))
    if len(matches)!=1:raise AssertionError('One visible native CarPlay name navigation row was expected: '+state)
    x,y,width,height=matches[0];session.tap(x+width//2,y+height//2)
    return validate_settings.wait_widget(session,name='RevivalNamePanel')


def aggregate(library,output,identity):
    library_hash=digest(library)
    reports={}
    for suite,filename in REPORTS.items():
        path=output/filename
        if path.exists():
            try:report=json.loads(path.read_text())
            except json.JSONDecodeError:continue # Another independent suite is finishing its report.
            if report.get('library_sha256')==library_hash and report.get('observer_sha256')==identity['observer_sha256']:
                reports[suite]=report
    naming=reports.get('settings',{})
    menu=reports.get('menu',{})
    clock=reports.get('clock',{})
    naming_ok=naming.get('passed') is True and naming.get('complete') is True and len(naming.get('cases',[]))==13
    menu_ok=menu.get('passed') is True and len(menu.get('cases',[]))==11
    clock_ok=clock.get('passed') is True and clock.get('clock_pixels_changed') is True and clock.get('clock_overlay_hidden_in_settings') is True
    report={'library_sha256':library_hash,'observer_sha256':identity['observer_sha256'],
            'passed':bool(naming_ok and menu_ok and clock_ok),
            'settings_case_count':len(naming.get('cases',[])),
            'menu_case_count':len(menu.get('cases',[])),
            'clock_passed':bool(clock_ok),
            'reports':{suite:str(output/REPORTS[suite]) for suite in reports},
            'historical_evidence_modified':False,
            'scope':'Fresh exact ARM candidate in the isolated Cloud native runtime, production P401_UI_LAB unset. Existing native naming, save/restart-request, footer/startup/fail-open, static repaint and natural clock/header checks with a freshly compiled separate plain observer. Private synthetic profiles/model fixtures and fake framebuffer; no physical radio, vehicle, reboot, full kernel boot, installation or recovery claim.'}
    (output/'REGRESSION_CHECKS.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--suite',choices=['all','settings','menu','clock'],default='all')
    parser.add_argument('--reuse-probe',action='store_true',help='Reuse only an observer whose source, binary and candidate identities still match.')
    parser.add_argument('--compile-probe-only',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    library=args.library.resolve();output=args.output_dir.resolve()
    if not output.is_relative_to(UI/'build/cloud/rc2'):
        raise ValueError('Use a separate output directory under experimental/ui1/build/cloud/rc2 to preserve old evidence.')
    output.mkdir(parents=True,exist_ok=True)
    expected=digest(library);candidate_build(library)
    if args.compile_probe_only:
        compile_probe(library,output);return
    if not args.reuse_probe:docker_compile(library,output)
    identity=check_probe(library,output)
    selected=list(REPORTS) if args.suite=='all' else [args.suite]
    # Remove only this invocation's previous suite reports. A failed rerun must
    # not leave a stale passing report or aggregate for the failed operation.
    for suite in selected:(output/REPORTS[suite]).unlink(missing_ok=True)
    (output/'REGRESSION_CHECKS.json').unlink(missing_ok=True)
    modules=[native,validate_settings,validate_menu,validate_clock]
    previous=[module.BUILD for module in modules]
    for module in modules:module.BUILD=output
    original_name_panel=validate_settings.name_panel
    validate_settings.name_panel=rc2_name_panel
    run={'library_sha256':expected,'observer_sha256':identity['observer_sha256'],
         'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'suite':args.suite,'passed':False}
    try:
        validators={'settings':validate_settings.validate,'menu':validate_menu.run,'clock':validate_clock.validate}
        for suite in selected:
            suite_report=validators[suite](library)
            suite_report['observer_sha256']=identity['observer_sha256']
            if suite=='settings':suite_report['navigation']='Read-only native Settings model label/visualRect observed, then real pointer tap on CarPlay name.'
            (output/REPORTS[suite]).write_text(json.dumps(suite_report,indent=2)+'\n')
        if digest(library)!=expected:raise AssertionError('Candidate library changed during the regression run.')
        if digest(output/PROBE_NAME)!=identity['observer_sha256']:raise AssertionError('Plain observer changed during the regression run.')
        report=aggregate(library,output,identity)
        run['passed']=True
        print(json.dumps({'completed_suite':args.suite,'all_regressions_passed':report['passed'],
                          'settings_cases':report['settings_case_count'],'menu_cases':report['menu_case_count'],
                          'clock_passed':report['clock_passed'],'library_sha256':expected,'output':str(output)},indent=2),flush=True)
        if args.suite=='all' and not report['passed']:raise AssertionError('Regression report is incomplete.')
    except BaseException as error:
        run['passed']=False;run['error']=str(error);raise
    finally:
        validate_settings.name_panel=original_name_panel
        for module,original in zip(modules,previous):module.BUILD=original
        run['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        (output/('RUN-'+args.suite+'.json')).write_text(json.dumps(run,indent=2)+'\n')


if __name__=='__main__':main()
