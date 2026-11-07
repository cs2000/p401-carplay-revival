"""Bind complete RC2 native/regression/storage evidence to one exact UI build.

This only aggregates fresh reports. It does not run tests or imply physical
radio, reboot, vehicle installation or full-flash recovery success.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

REPO = Path(__file__).resolve().parents[4]
UI = REPO / 'experimental/ui1'
sys.path.insert(0, str(REPO / 'tools'))
from package_ui1_candidate import source_snapshot

FEATURE_CASES = {'connection-native-events', 'appearance-pointer-save',
                 'appearance-cancel', 'appearance-reload-native-routing',
                 'settings-native-advanced'}
NAME_CASES = {'type3', 'busy-restart-lock', 'whitespace-crlf', 'general-case',
              'quoted-type', 'lowercase-key', 'unsupported', 'invalid-type',
              'missing-key', 'missing-file', 'reload-saved', 'maximum-name',
              'invalid-saved-file'}
MENU_CASES = {'unknown-exit-classification-and-original-native-footer-actions',
              'static-menu-does-not-repaint',
              'model-empty-restores-stock-without-flicker',
              'model-missing-restores-stock-without-flicker',
              'model-unknown-only-restores-stock-without-flicker',
              'model-exit-only-restores-stock-without-flicker',
              'model-main-only-restores-stock-without-flicker',
              'initial-empty-waits-for-model', 'initial-missing-waits-for-model',
              'hidden-launcher-ready-without-forcing-home-visible',
              'invalid-model-timeout-fails-open'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def passed_tree(value):
    if isinstance(value, dict):
        assert 'passed' not in value or value['passed'] is True, 'Failed embedded check'
        for child in value.values():
            passed_tree(child)
    elif isinstance(value, list):
        for child in value:
            passed_tree(child)


def aggregate(library, features, regression, preferences, output):
    # Remove only this tool's output before checking inputs, so a failed rerun
    # cannot leave an earlier green aggregate looking current.
    assert output.resolve().is_relative_to((UI / 'build').resolve()), 'Use ignored UI build output'
    output.unlink(missing_ok=True)
    library_hash = sha(library)
    build = json.loads((UI / 'build/BUILD.json').read_text())
    assert build['sha256'] == library_hash, 'BUILD.json identifies another binary'
    paths = {'features': features,
             'naming': regression / 'SETTINGS_CLOUD_CHECKS.json',
             'menu': regression / 'MENU_CLOUD_CHECKS.json',
             'clock': regression / 'CLOCK_CLOUD_CHECKS.json',
             'preferences_storage': preferences}
    reports = {key: json.loads(path.read_text()) for key, path in paths.items()}
    for key, report in reports.items():
        assert report.get('passed') is True, 'Incomplete report: ' + key
        passed_tree(report)
        if key != 'preferences_storage':
            assert report['library_sha256'] == library_hash, 'Different binary: ' + key
    feature, names, menu, clock, storage = (reports[key] for key in paths)
    for report, expected in [(feature, FEATURE_CASES), (names, NAME_CASES), (menu, MENU_CASES)]:
        assert {case['case'] for case in report['cases']} == expected, 'Incomplete case matrix'
        assert len(report['cases']) == len(expected), 'Duplicate test case'
    assert feature.get('complete') is True and names.get('complete') is True
    assert clock['clock_pixels_changed'] is True and clock['clock_overlay_hidden_in_settings'] is True
    assert len(storage['checks']) == 23, 'Incomplete storage matrix'
    for relative, expected in storage['sources'].items():
        assert sha(UI / relative) == expected, 'Storage-tested source changed: ' + relative
    identity = json.loads((regression / 'PROBE.json').read_text())
    assert identity['library_sha256'] == library_hash and identity['plain_observer'] is True
    assert sha(regression / 'libp401-test-probe.so') == identity['observer_sha256']
    for key in ('naming', 'menu', 'clock'):
        assert reports[key]['observer_sha256'] == identity['observer_sha256'], 'Observer mismatch: ' + key
    assert sha(UI / 'build/cloud/libp401-rc2-test-probe.so') == feature['observer_sha256']
    snapshot = source_snapshot()
    result = {'schema_version': 2, 'variant': 'rc2', 'passed': True, 'complete': True,
              'library_sha256': library_hash, 'build': build, 'source_snapshot': snapshot,
              'cases': [{'case': key, 'passed': True} for key in paths],
              'reports': reports,
              'report_files': {key: {'file': str(path.relative_to(REPO)),
                                     'bytes': path.stat().st_size, 'sha256': sha(path)}
                               for key, path in paths.items()},
              'physical_device_tested': False, 'hardware_radio_tested': False,
              'hardware_reboot_tested': False, 'full_flash_recovery_proven': False,
              'historical_evidence_modified': False,
              'scope': 'Fresh exact ARM UI feature, naming, menu/startup and natural clock checks in isolated offline Docker/QEMU with separate observers, synthetic private profiles/model/status fixtures and fake framebuffer. Storage checks compile the exact unchanged production preferences sources separately. No physical radios, iPhone/MFi session, MCU, reboot, kernel boot, vehicle installation or full-flash recovery are emulated.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'complete': True, 'library_sha256': library_hash,
                      'source_snapshot_sha256': snapshot['sha256'], 'output': str(output)}, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=UI / 'build/libp401-ui.so')
    parser.add_argument('--features', type=Path, default=UI / 'build/cloud/rc2/RC2_FEATURE_CHECKS.json')
    parser.add_argument('--regression-dir', type=Path, default=UI / 'build/cloud/rc2/regression')
    parser.add_argument('--preferences', type=Path, default=UI / 'build/cloud/preferences/RESULT.json')
    parser.add_argument('--output', type=Path, default=UI / 'build/cloud/rc2/NATIVE_EVIDENCE.json')
    args = parser.parse_args()
    aggregate(args.library.resolve(), args.features.resolve(), args.regression_dir.resolve(),
              args.preferences.resolve(), args.output.resolve())
