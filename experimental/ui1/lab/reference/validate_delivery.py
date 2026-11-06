"""ARM BusyBox/CRC checks; controlled process fixtures exercise launch failures."""
from pathlib import Path
import subprocess, os, json, tempfile, zlib, shlex, hashlib

WS=Path('/opt/p401-workspace')
SRC=WS/'work/ui_customization';AUTO=SRC/'delivery/install/msn_autocopy'
BASE=WS/'outputs/P401_W3_FIELD_LOGS_2026-11-06/P401_W3_INSTALLED_PAYLOAD'
VENDOR=Path('/opt/p401-build/candidate-r1/root')
arm=['qemu-arm','-L',str(VENDOR),str(VENDOR/'bin/busybox'),'sh']
helper=['qemu-arm',str(WS/'work/logger_r4/build/p401-diag')]
area=Path(tempfile.mkdtemp(prefix='p401-ui-delivery-',dir='/opt'))
checks=[]
def check(label,ok):
    checks.append({'check':label,'passed':bool(ok)});print(('PASS ' if ok else 'FAIL ')+label,flush=True);assert ok,label
def crc(b):return f'{zlib.crc32(b):08x} {len(b)}'
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s);p.chmod(0o755)
def run(args,**kw):return subprocess.run(args,capture_output=True,timeout=20,**kw)

for path in AUTO.rglob('*.sh'):check('ARM shell syntax '+path.name,run(arm+['-n',str(path)]).returncode==0)
for manifest in ['data/p401-w3/install-checks.txt','data/carplay-revival/compatibility.txt']:
    for line in (AUTO/manifest).read_text().splitlines():
        checksum,size,absolute=line.split(' ',2);rel=absolute.lstrip('/')
        candidates=[AUTO/rel,BASE/rel,WS/'work/wifi_w2/usb/msn_autocopy'/rel,VENDOR/rel]
        p=next((p for p in candidates if p.is_file()),None)
        check('verified '+absolute,p is not None and run(helper+['verify',str(p),checksum,size]).returncode==0)
back=SRC/'delivery/rollback/msn_autocopy'
for rel in ['usr/bin/p401-recovery-run-core.sh','data/p401-w3/install-checks.txt']:
    check('rollback exact prior '+rel,(back/rel).read_bytes()==(BASE/rel).read_bytes())
old=(BASE/'data/p401-w3/install-checks.txt').read_text().splitlines()
new=(AUTO/'data/p401-w3/install-checks.txt').read_text().splitlines()
check('only GUI runner changes in W3 manifest',len(old)==len(new) and all(a==b or a.endswith('/usr/bin/p401-recovery-run-core.sh') and b.endswith('/usr/bin/p401-recovery-run-core.sh') for a,b in zip(old,new)))
allowed={'usr/bin/p401-recovery-run-core.sh','data/p401-w3/install-checks.txt'}
check('no kernel, MCU, firmware or user profile replacement',all(p.relative_to(AUTO).as_posix() in allowed or p.relative_to(AUTO).as_posix().startswith('data/carplay-revival/') for p in AUTO.rglob('*') if p.is_file()))

f=area/'fixture';data=f/'data/carplay-revival';tmp=f/'tmp';tmp.mkdir(parents=True)
write(f/'helper','#!/bin/sh\nexec '+shlex.join(helper)+' "$@"\n')
write(f/'bin/MsnCoreApp','''#!/bin/sh
if [ -n "$P401_TEST_PRELOAD" ]; then
  echo "CUSTOM names=$P401_UI_NAMES"
  case "$CASE" in
    crash) exit 139;;
    notready) exit 0;;
    timeout) exec sleep 8;;
    *) echo ready > "$FIXTURE/tmp/p401-ui-ready"; exit 0;;
  esac
else
  echo STOCK
fi
''')
library=data/'lib/libp401-ui.so';library.parent.mkdir(parents=True)
library.write_bytes((AUTO/'data/carplay-revival/lib/libp401-ui.so').read_bytes())
rows=[]
for line in (AUTO/'data/carplay-revival/compatibility.txt').read_text().splitlines():
    checksum,size,absolute=line.split(' ',2)
    p=library if absolute.endswith('/libp401-ui.so') else VENDOR/absolute.lstrip('/')
    rows.append(f'{checksum} {size} {p}\n')
fixture_manifest=''.join(rows)
original=(AUTO/'data/carplay-revival/run-ui.sh').read_text()
original_crc=crc((AUTO/'data/carplay-revival/compatibility.txt').read_bytes())
script=original.replace('/data/carplay-revival',str(data)).replace('/usr/lib/p401-r4/p401-diag',str(f/'helper')).replace('/msnprofile/',str(f/'msnprofile')+'/').replace('/tmp/p401-ui-',str(tmp/'p401-ui-')).replace('/tmp/p401-w3-install-ok',str(tmp/'p401-w3-install-ok'))
script=script.replace(original_crc,crc(fixture_manifest.encode()))
# Process launch is recorded instead of loading ARM Qt into a host shell stub.
script=script.replace('LD_PRELOAD=', 'P401_TEST_PRELOAD=').replace('[ "$ticks" -lt 60 ]','[ "$ticks" -lt 2 ]')
write(f/'run-ui.sh',script)
for case in ['healthy','unsupported-bt','disabled','no-w3','corrupt-manifest','corrupt-library','crash','notready','timeout']:
    for p in tmp.glob('p401-*'):p.unlink()
    write(data/'state','disabled\n' if case=='disabled' else 'enabled\n')
    write(tmp/'p401-w3-install-ok','verified\n')
    if case=='no-w3':(tmp/'p401-w3-install-ok').unlink()
    write(data/'compatibility.txt',fixture_manifest)
    library.write_bytes((AUTO/'data/carplay-revival/lib/libp401-ui.so').read_bytes())
    if case=='corrupt-library':library.write_bytes(b'bad library')
    if case=='corrupt-manifest':write(data/'compatibility.txt','bad manifest\n')
    profile='[General]\nMcuType=6\nBlueToothType='+('5' if case=='unsupported-bt' else '3')+'\n'
    write(f/'msnprofile/MsnProductInfo.ini',profile)
    env=dict(os.environ,PATH=str(f/'bin')+':'+os.environ['PATH'],CASE=case,FIXTURE=str(f))
    r=run(arm+[str(f/'run-ui.sh')],env=env);output=r.stdout.decode()
    custom='CUSTOM names=' in output;stock='STOCK' in output
    if case=='healthy':ok=custom and 'names=1' in output and not stock
    elif case=='unsupported-bt':ok=custom and 'names=0' in output and not stock
    elif case in ['crash','notready','timeout']:ok=custom and stock and (data/'state').read_text()=='disabled\n'
    else:ok=stock and not custom
    check(case+' launch/fallback',r.returncode==0 and ok)
    check(case+' preserves factory profile',(f/'msnprofile/MsnProductInfo.ini').read_text()==profile)
result={'passed':True,'checks':checks,'fixture':str(area),'scope':'Actual ARM BusyBox and CRC verifier, redirected filesystem, recorded GUI process launches; no physical device.'}
(SRC/'tests/evidence/DELIVERY_CHECKS.json').write_text(json.dumps(result,indent=2)+'\n')
print('All delivery checks passed.',flush=True)
