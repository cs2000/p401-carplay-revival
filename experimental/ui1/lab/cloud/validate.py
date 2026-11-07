"""Aggregate completed fresh native reports for one exact candidate library.

This does not run tests or convert archived historical results into fresh evidence.
Run validate_settings.py, validate_menu.py and the documented clock check first.
"""
from pathlib import Path
import argparse,hashlib,json
from native import BUILD,UI


def aggregate(library,paths,output):
    digest=hashlib.sha256(library.read_bytes()).hexdigest()
    reports={}
    cases=[]
    for path in paths:
        report=json.loads(path.read_text())
        assert report.get('passed') is True,'Incomplete/failed report: '+str(path)
        assert report['library_sha256']==digest,'Report is for another binary: '+str(path)
        for group in ['cases','checks']:
            for case in report.get(group,[]):
                if isinstance(case,dict) and 'passed' in case:
                    assert case['passed'] is True,(path,case)
        if path.name=='SETTINGS_CLOUD_CHECKS.json':
            assert report.get('complete') is True,'Settings matrix is incomplete'
            required={'type3','whitespace-crlf','general-case','quoted-type','lowercase-key','unsupported','invalid-type','missing-key','missing-file','reload-saved','maximum-name','invalid-saved-file'}
            assert required<={case['case'] for case in report['cases']},'Missing Settings cases'
        if path.name=='MENU_CLOUD_CHECKS.json':
            required={'unknown-exit-classification-and-original-native-footer-actions','static-menu-does-not-repaint','model-empty-restores-stock-without-flicker','model-missing-restores-stock-without-flicker','model-unknown-only-restores-stock-without-flicker','model-exit-only-restores-stock-without-flicker','model-main-only-restores-stock-without-flicker','initial-empty-waits-for-model','initial-missing-waits-for-model','hidden-launcher-ready-without-forcing-home-visible','invalid-model-timeout-fails-open'}
            assert required<={case['case'] for case in report['cases']},'Missing startup/menu cases'
        reports[path.name]=report
        cases.append({'case':path.stem,'passed':True})
    result={'schema_version':1,'library_sha256':digest,'passed':True,'cases':cases,'reports':reports,
            'scope':'Fresh actual ARM GUI checks in private Docker network/PID/IPC, synthetic profiles, test-only observability and fake framebuffer. See embedded reports for exact fixtures and limits.',
            'physical_device_tested':False,'hardware_radio_tested':False,'hardware_reboot_tested':False,'historical_evidence_modified':False}
    output.write_text(json.dumps(result,indent=2)+'\n')
    print('PASS fresh native reports for',digest)
    print(output)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library',type=Path,default=UI/'build/libp401-ui.so')
    p.add_argument('--reports',nargs='+',type=Path,default=[BUILD/'CLOCK_CLOUD_CHECKS.json',BUILD/'SETTINGS_CLOUD_CHECKS.json',BUILD/'MENU_CLOUD_CHECKS.json'])
    p.add_argument('--output',type=Path,default=BUILD/'NATIVE_CLOUD_CHECKS.json')
    a=p.parse_args();aggregate(a.library,a.reports,a.output)
