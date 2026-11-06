"""Prepare the UI overlay and exact prior-state rollback; never writes a USB."""
from pathlib import Path
import hashlib, json, shutil, zipfile, zlib

SRC=Path(__file__).resolve().parent;WS=SRC.parents[1]
BASE=WS/'outputs/P401_W3_FIELD_LOGS_2026-11-06/P401_W3_INSTALLED_PAYLOAD'
VENDOR=WS/'work/rootfs/24958429/rootfs'
OUT=WS/'outputs/P401_XFR_UI1';OUT.mkdir(exist_ok=True)
def checksum(b):return f'{zlib.crc32(b):08x} {len(b)}'
def write(root,name,b):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(b.encode() if isinstance(b,str) else b)
def archive(root,path):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(root.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(root).as_posix())
    return {'file':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

binary=(SRC/'build/libp401-ui.so').read_bytes()
evidence=json.loads((SRC/'tests/evidence/NATIVE_CHECKS.json').read_text())
assert evidence['passed'] and evidence['library_sha256']==hashlib.sha256(binary).hexdigest()
install=SRC/'delivery/install';rollback=SRC/'delivery/rollback'
auto=install/'msn_autocopy';back=rollback/'msn_autocopy'
write(auto,'data/carplay-revival/lib/libp401-ui.so',binary)
rows=[checksum(binary)+' /data/carplay-revival/lib/libp401-ui.so\n']
for rel in ['usr/bin/MsnCoreApp','usr/lib/libBlueTooth.so','usr/lib/libLauncher-Box.so','usr/lib/libSetting.so','usr/lib/libMsnCommons.so','usr/local/Qt4.7.4/lib/libQtCore.so.4.7.4','usr/local/Qt4.7.4/lib/libQtGui.so.4.7.4','lib/libstdc++.so.6','lib/libc.so.6']:
    aliases={'lib/libstdc++.so.6':'lib/libstdc++.so.6.0.20','lib/libc.so.6':'lib/libc-2.27.so'}
    p=VENDOR/aliases.get(rel,rel)
    if p.is_symlink():p=p.resolve()
    if not p.exists():
        # Windows extraction represents some Unix symlinks as tiny text files.
        raise FileNotFoundError(rel)
    rows.append(checksum(p.read_bytes())+' /'+rel+'\n')
manifest=''.join(rows).encode();write(auto,'data/carplay-revival/compatibility.txt',manifest)
launch=(SRC/'run-ui.sh.in').read_text().replace('@MANIFEST_CHECK@',checksum(manifest)).encode()
write(auto,'data/carplay-revival/run-ui.sh',launch);write(auto,'data/carplay-revival/state','enabled\n')
old=(BASE/'usr/bin/p401-recovery-run-core.sh').read_bytes()
line=b'MsnCoreApp -qws 2>&1 | /bin/sh /usr/bin/p401-log-stream.sh core'
assert old.count(line)==1
replacement=('if "$helper" verify /data/carplay-revival/run-ui.sh '+checksum(launch)+'; then\n'
'    /bin/sh /data/carplay-revival/run-ui.sh 2>&1 | /bin/sh /usr/bin/p401-log-stream.sh core\n'
'else\n    '+line.decode()+'\nfi').encode()
new=old.replace(line,replacement);write(auto,'usr/bin/p401-recovery-run-core.sh',new)
old_checks=(BASE/'data/p401-w3/install-checks.txt').read_bytes()
old_row=(checksum(old)+' /usr/bin/p401-recovery-run-core.sh').encode()
assert old_checks.count(old_row)==1
write(auto,'data/p401-w3/install-checks.txt',old_checks.replace(old_row,(checksum(new)+' /usr/bin/p401-recovery-run-core.sh').encode()))
write(back,'usr/bin/p401-recovery-run-core.sh',old)
write(back,'data/p401-w3/install-checks.txt',old_checks)
write(back,'data/carplay-revival/state','disabled\n')
readme='''P401 XFR UI1 â€” experimental menu and custom CarPlay name

For the existing R1 + W3 installation used in this project. This is a small
overlay, not a standalone firmware image. Do not apply it to unrelated firmware.

WHAT CHANGES
Six main tiles, permanent Exit and Settings buttons, turquoise illumination,
and the stacked Jaguar leaper/wordmark centred above the middle column.
Exit uses the original AV in action.
Settings > CarPlay name changes both Wi-Fi and Bluetooth after Save & restart.
Names may contain 1-24 English letters, digits, spaces, hyphens and underscores.
The name option is enabled for Bluetooth type 3 (SD-RDA). MCU settings are preserved.

INSTALL
1. Extract INSTALL.zip. Put its msn_autocopy folder at the root of a FAT32 USB.
   Use only this active msn_autocopy folder; keep other update payloads off the USB.
2. Insert it into the running box and wait for autocopy to finish.
3. Remove the USB, then fully power-cycle the box. The new main menu should appear.
4. To rename it, open Settings > CarPlay name > Change name. Enter the name,
   Continue, then Save & restart. You may need to forget the old pairing on your
   iPhone and pair again. The change applies after restart, not during a connection.

UNDO
Use the msn_autocopy folder from ROLLBACK.zip the same way. It restores the exact
previous GUI runner and W3 activation manifest. Existing wireless CarPlay fixes
remain. A saved custom name is ignored; the native default name returns.

The extension checks matching vendor files before loading. It falls back to the
original interface if those checks fail, and attempts a stock-interface restart
if the modified GUI exits abnormally or does not become ready within 60 seconds.
This is not a recovery route for a box that cannot boot or accept USB updates.

STATUS AND RISK
The real ARM GUI, name persistence, Bluetooth requested-name generation, Wi-Fi
configuration and CarPlay SSID advertisement have passed isolated PC tests.
The physical radio and automatic hardware reboot have not yet been tested with
this extension. The existing W3 wireless fix has worked on the real box.
This update does not back up your firmware. Flashing/installing is at your own
risk. I offer no recovery method if the unit becomes unbootable.
'''
write(OUT,'READ_ME.txt',readme)
source=SRC/'delivery/source'
for name in ['ui.cpp','name_store.cpp','name_store.h','name_hooks.cpp','lab_probe.cpp','brand_paths.h','r_badge.h','trace_brand.py','make_brand.py','build.py','run-ui.sh.in','prepare_ui.py','validate_native.py','validate_delivery.py']:
    write(source,name,(SRC/name).read_bytes())
for name in ['jaguar-stacked.svg','jaguar-reference.png','r-badge-reference.png','branding-source.json']:write(source,'assets/'+name,(SRC/'assets'/name).read_bytes())
for name in ['LICENSE.LGPL','LGPL_EXCEPTION.txt']:write(source,'qt/'+name,(WS/'work/qt4-headers'/name).read_bytes())
write(source,'LICENSE',(WS/'work/p401-carplay-revival/LICENSE').read_bytes())
write(source,'THIRD_PARTY.txt','Qt 4.7.4 headers: https://github.com/qt/qt/tree/v4.7.4, LGPL 2.1 with Qt exception.\nLinks dynamically to the existing vendor Qt libraries. No replacement Qt library is included.\nJaguar artwork remains a Jaguar trademark; it is not licensed under the source-code MIT licence.\nSource artwork provenance is in assets/branding-source.json.\n')
items=[archive(install,OUT/'INSTALL.zip'),archive(rollback,OUT/'ROLLBACK.zip'),archive(source,OUT/'SOURCE.zip')]
write(OUT,'MANIFEST.json',json.dumps({'packages':items,'native_checks':evidence,'flash_backup':False,'published':False},indent=2)+'\n')
print(json.dumps(items,indent=2))
