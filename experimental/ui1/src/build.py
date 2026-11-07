"""Build against the matching vendor Qt ABI; run inside the existing WSL lab."""
from pathlib import Path
import subprocess, shutil, json, hashlib, os

SRC = Path(__file__).resolve().parent
UI = SRC.parent
QT = Path(os.environ.get('P401_QT_HEADERS', UI/'inputs/qt4-headers'))
VENDOR = Path(os.environ.get('P401_VENDOR_ROOT', UI/'inputs/vendor-root'))
ARM_HEADERS = Path(os.environ.get('P401_ARM_HEADERS', UI/'inputs/arm-headers'))
SDK = UI/'build/include'
OUT = UI/'build'
OUT.mkdir(parents=True, exist_ok=True)
for required in [QT/'src/corelib', VENDOR/'usr/bin/MsnCoreApp', ARM_HEADERS/'features.h']:
    if not required.exists():
        raise SystemExit('Missing build input: '+str(required)+'; see experimental/ui1/BUILDING.md')
OUT.mkdir(exist_ok=True)
SDK.mkdir(parents=True, exist_ok=True)
# Embed the prepared static artwork; installation keeps the six-file contract.
artwork=(SRC/'assets/glass-tile-atlas.png').read_bytes()
rows=[','.join('0x%02x'%b for b in artwork[i:i+16]) for i in range(0,len(artwork),16)]
(SDK/'glass_artwork.h').write_text('// Generated from assets/glass-tile-atlas.png.\n'
    'static const unsigned char p401_glass_tile_atlas[]={\n'+',\n'.join(rows)+'\n};\n'
    'static const unsigned int p401_glass_tile_atlas_size=sizeof(p401_glass_tile_atlas);\n')
for module, sub in [('QtCore','corelib'), ('QtGui','gui'), ('QtNetwork','network')]:
    dest = SDK/module
    dest.mkdir(parents=True, exist_ok=True)
    for header in (QT/'src'/sub).rglob('*.h'):
        # Qt's generated public forwarding headers are not in its git tree.
        target=dest/header.name
        if not target.exists():
            target.write_text('#include "'+str(header)+'"\n')
(SDK/'QtCore/qconfig.h').write_text('''#ifndef P401_QCONFIG_H
#define P401_QCONFIG_H
#define QT_SHARED
#define QT_EDITION QT_EDITION_OPENSOURCE
#define QT_ARCH_ARM
#define Q_WS_QWS
#define QT_NO_STL
#define QT_NO_EXCEPTIONS
#define QT_LARGEFILE_SUPPORT 64
#define Q_BYTE_ORDER 1234
#define Q_LITTLE_ENDIAN 1234
#define Q_BIG_ENDIAN 4321
#define QT_POINTER_SIZE 4
#endif
''')
# No C++ runtime implementation is supplied; the vendor runtime resolves new/delete.
(SDK/'new').write_text('''#ifndef P401_NEW_DECLARATIONS
#define P401_NEW_DECLARATIONS
#include <stddef.h>
void *operator new(size_t);
void *operator new[](size_t);
void operator delete(void *) noexcept;
void operator delete[](void *) noexcept;
inline void *operator new(size_t, void *p) noexcept { return p; }
inline void *operator new[](size_t, void *p) noexcept { return p; }
inline void operator delete(void *, void *) noexcept {}
inline void operator delete[](void *, void *) noexcept {}
#endif
''')
qtl = VENDOR/'usr/local/Qt4.7.4/lib'
libs=[qtl/'libQtGui.so.4.7.4',qtl/'libQtCore.so.4.7.4',VENDOR/'lib/libstdc++.so.6',VENDOR/'lib/libc.so.6',VENDOR/'lib/libdl.so.2',VENDOR/'lib/libm.so.6']
cmd=['clang++','--target=arm-linux-gnueabihf','-march=armv7-a','-mfpu=vfpv3-d16','-mfloat-abi=hard',
     '-isystem',str(ARM_HEADERS),'-I'+str(SDK),'-I'+str(SDK/'QtCore'),'-I'+str(SDK/'QtGui'),
     '-fuse-ld=lld','-fPIC','-shared','-nostdlib','-nostdinc++','-fno-exceptions','-fno-rtti',
     '-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
     '-Wl,--hash-style=both,-soname,libp401-ui.so','-std=c++11','-O2','-Wall','-Wextra','-Wno-deprecated','-Wno-reserved-user-defined-literal',
     str(SRC/'ui.cpp'),str(SRC/'name_store.cpp'),str(SRC/'name_hooks.cpp'),str(SRC/'lab_probe.cpp'),*[str(p) for p in libs],'-o',str(OUT/'libp401-ui.so')]
r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
(OUT/'build.log').write_text(r.stdout)
if r.returncode:
    print('\n'.join(l for l in r.stdout.splitlines() if 'error:' in l or 'undefined symbol' in l));raise SystemExit(r.returncode)
b=(OUT/'libp401-ui.so').read_bytes()
(OUT/'BUILD.json').write_text(json.dumps({'qt_tag':'v4.7.4','qt_commit':'092cd760d5fddf9640a310214fe01929f0fff3a8','qreal':'float (verified vendor symbol ABI)','bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'command':cmd},indent=2)+'\n')
print('Built ARM Qt extension:',len(b),'bytes',hashlib.sha256(b).hexdigest())
