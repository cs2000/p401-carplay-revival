"""Read-only verification of the exact UI1 migration artifacts (no device needed)."""
from pathlib import Path
import hashlib
import json
import zipfile
import zlib

repo=Path(__file__).resolve().parents[1]
ui=repo/'experimental/ui1'
manifest=json.loads((ui/'packages/MANIFEST.json').read_text())
sha=lambda data:hashlib.sha256(data).hexdigest()
payloads={}
for package in manifest['packages']:
    path=ui/'packages'/package['file']
    assert path.stat().st_size==package['bytes'],path
    assert sha(path.read_bytes())==package['sha256'],path
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None,path
        files={i.filename:archive.read(i) for i in archive.infolist() if not i.is_dir()}
        assert set(files)==set(package['files']),path
        assert all(n.startswith('msn_autocopy/') and '..' not in Path(n).parts for n in files)
        for name,data in files.items():
            expected=package['files'][name]
            assert len(data)==expected['bytes'] and sha(data)==expected['sha256'],name
        payloads[package['file']]=files
    print('PASS',package['file'],package['sha256'])

install=payloads['INSTALL.zip'];rollback=payloads['ROLLBACK.zip']
prefix='msn_autocopy/'
assert len(install)==6 and len(rollback)==3
library=install[prefix+'data/carplay-revival/lib/libp401-ui.so']
assert sha(library)==manifest['library_sha256']
assert sha((repo/'releases/2026.11-w3-rc1/P401_2026.11_W3_RC1.zip').read_bytes())=='826592230326d57be22895fc89a1228504a16d45015c5996e5d6cca4c1e02278'
for name,data in rollback.items():
    assert data==(ui/'baseline'/name.removeprefix(prefix)).read_bytes(),name
assert rollback[prefix+'data/carplay-revival/state']==b'disabled\n'
assert install[prefix+'data/carplay-revival/state']==b'enabled\n'
old=rollback[prefix+'data/p401-w3/install-checks.txt'].decode().splitlines()
new=install[prefix+'data/p401-w3/install-checks.txt'].decode().splitlines()
assert len(old)==len(new)
changed=[(a,b) for a,b in zip(old,new) if a!=b]
assert len(changed)==1 and all(x.endswith(' /usr/bin/p401-recovery-run-core.sh') for x in changed[0])
for files in [install,rollback]:
    runner=files[prefix+'usr/bin/p401-recovery-run-core.sh']
    row=f'{zlib.crc32(runner):08x} {len(runner)} /usr/bin/p401-recovery-run-core.sh'
    assert row in files[prefix+'data/p401-w3/install-checks.txt'].decode().splitlines()
native=json.loads((ui/'evidence/NATIVE_CHECKS.json').read_text())
delivery=json.loads((ui/'evidence/DELIVERY_CHECKS.json').read_text())
assert native['passed'] and native['library_sha256']==sha(library)
assert len(native['cases'])==4 and all(c['passed'] for c in native['cases'])
assert delivery['passed'] and len(delivery['checks'])==52 and all(c['passed'] for c in delivery['checks'])
print('PASS exact rollback, unchanged stable release, runner checksums and historical evidence')
print('This verifies archived artifacts; it does not run the ARM GUI or establish physical-device success.')
