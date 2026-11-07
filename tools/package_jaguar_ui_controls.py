"""Create state-only UI rollback/re-enable ZIPs for the standalone Jaguar image.

These do not restore firmware or write MCU/factory settings. No device is opened.
"""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

PAYLOAD = 'msn_autocopy/data/carplay-revival/state'


def create(output):
    output.mkdir(parents=True, exist_ok=False)
    packages = []
    for name, state in [('UI_ROLLBACK.zip', b'disabled\n'), ('ENABLE_JAGUAR_UI.zip', b'enabled\n')]:
        path = output / name
        info = zipfile.ZipInfo(PAYLOAD, (2026, 11, 7, 0, 0, 0))
        info.create_system = 3
        info.external_attr = 0o100644 << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr(info, state)
        with zipfile.ZipFile(path) as archive:
            assert archive.namelist() == [PAYLOAD] and archive.read(PAYLOAD) == state
            assert archive.testzip() is None
        data = path.read_bytes()
        packages.append({'file': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                         'files': {PAYLOAD: {'bytes': len(state), 'sha256': hashlib.sha256(state).hexdigest()}}})
    result = {'target': '2026.11-jaguar-xfr-rc1 standalone UI launcher', 'packages': packages,
              'operation': 'Only write the Jaguar UI enable/disable state; retain W3 and saved network name.',
              'requires_booting_unit_and_autocopy': True, 'firmware_backup': False,
              'full_flash_recovery': False, 'factory_or_mcu_settings_written': False}
    (output / 'UI_CONTROLS.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    create(parser.parse_args().output.resolve())
