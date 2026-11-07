"""Validate rebuilt UBI media, complete filesystem inventory and ELF closure.

All checks are offline. No result is a claim of target board compatibility.
"""
import collections
import hashlib
import io
import json
from pathlib import Path
import posixpath
import stat
import struct
import tarfile
import zlib
from elftools.elf.elffile import ELFFile
from ubireader.ubi import ubi
from ubireader.ubifs import ubifs
from ubireader.ubi_io import ubi_file, leb_virtual_file

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def medium(path):
    data = path.read_bytes()
    assert len(data)%131072 == 0
    headers=0; nodes=0; vt_records=0
    node_types=collections.Counter()
    for offset in range(0,len(data),131072):
        block=data[offset:offset+131072]
        assert block[:4]==b'UBI#', (offset, 'EC magic')
        assert struct.unpack_from('>I',block,60)[0]==(~zlib.crc32(block[:60])&0xffffffff)
        vid_off, data_off=struct.unpack_from('>II',block,16)
        assert (vid_off,data_off)==(2048,4096)
        vid=block[vid_off:vid_off+64]
        assert vid[:4]==b'UBI!'
        assert struct.unpack_from('>I',vid,60)[0]==(~zlib.crc32(vid[:60])&0xffffffff)
        headers+=2
        volid=struct.unpack_from('>I',vid,8)[0]
        if volid==0x7fffefff:
            for n in range(128):
                rec=block[data_off+n*172:data_off+(n+1)*172]
                assert struct.unpack_from('>I',rec,168)[0]==(~zlib.crc32(rec[:168])&0xffffffff)
                vt_records+=1
            continue
        assert volid==0
        leb=block[data_off:]
        for pos in range(0,len(leb)-24,8):
            if leb[pos:pos+4]!=b'\x31\x18\x10\x06': continue
            size=struct.unpack_from('<I',leb,pos+16)[0]
            assert 24<=size<=len(leb)-pos, (offset,pos,size)
            crc=struct.unpack_from('<I',leb,pos+4)[0]
            assert crc==(~zlib.crc32(leb[pos+8:pos+size])&0xffffffff),(offset,pos,'node CRC')
            nodes+=1;node_types[leb[pos+20]]+=1
    u=ubi(ubi_file(str(path),131072))
    assert len(u.images)==1 and len(u.images[0].volumes)==1
    v=list(u.images[0].volumes.values())[0]
    b=ubifs(leb_virtual_file(u,v.get_blocks(u.blocks)))
    fields=['flags','fmt_version','ro_compat_version','min_io_size','leb_size','leb_cnt',
        'max_leb_cnt','log_lebs','lpt_lebs','orph_lebs','jhead_cnt','fanout','default_compr','max_bud_bytes','rp_size']
    sb={k:getattr(b.superblock_node,k) for k in fields}
    assert sb['fmt_version']==4 and sb['ro_compat_version']==0 and sb['flags']==4
    assert v.vol_rec.flags==1 and v.vol_rec.name==b'rootfs'
    assert v.vol_rec.reserved_pebs==sb['leb_cnt'] and sb['leb_cnt'] <= 840
    return {'bytes':len(data),'sha256':sha(path),'ubi_header_crcs':headers,'volume_table_crcs':vt_records,
        'ubifs_common_node_crcs':nodes,'node_types':dict(node_types),'superblock':sb,
        'ubi_volume_name':'rootfs','ubi_volume_id':0,'autoresize':True,'volume_reserved_pebs':v.vol_rec.reserved_pebs}

def dependencies(tarpath, extra_seeds=()):
    with tarfile.open(tarpath) as tf:
        members={x.name:x for x in tf.getmembers()}
        def resolve(p):
            p=posixpath.normpath(p).lstrip('/')
            for _ in range(20):
                if p not in members:return None
                m=members[p]
                if not m.issym():return p
                p=posixpath.normpath(m.linkname if m.linkname.startswith('/') else posixpath.join(posixpath.dirname(p),m.linkname)).lstrip('/')
            raise AssertionError('Symlink loop: '+p)
        directories=['lib','usr/lib','usr/local/Qt4.7.4/lib']
        seeds=['usr/bin/MsnFirstInit','usr/bin/MsnCoreApp','usr/bin/gocsdk','usr/bin/carplay',
            'usr/bin/hostapd','usr/lib/libMcuCenter.so','usr/lib/libBlueTooth.so',
            'usr/lib/libMsnCarPlay.so','usr/lib/libLauncher-Box.so','usr/lib/libSetting.so']
        # Preloaded extensions do not appear in the vendor executables' normal
        # DT_NEEDED closure. Keep the RC1 defaults and explicitly seed additions.
        seeds=list(dict.fromkeys(seeds+list(extra_seeds)))
        todo=seeds[:];done={}
        while todo:
            p=resolve(todo.pop())
            assert p
            if p in done:continue
            data=tf.extractfile(members[p]).read()
            elf=ELFFile(io.BytesIO(data))
            assert elf.header['e_machine']=='EM_ARM',p
            needed=[];resolved={}
            dyn=elf.get_section_by_name('.dynamic')
            if dyn:
                needed=[x.needed for x in dyn.iter_tags() if x.entry.d_tag=='DT_NEEDED']
            for name in needed:
                found=next((r for d in directories if (r:=resolve(d+'/'+name))),None)
                assert found,(p,name)
                resolved[name]=found;todo.append(found)
            ignored_dso_interpreters=[]
            for segment in elf.iter_segments():
                if segment.header.p_type=='PT_INTERP':
                    interp=segment.get_interp_name()
                    # PT_INTERP is used when the kernel executes a program, not
                    # when a shared library is loaded through DT_NEEDED/dlopen.
                    # The supplied ARM QtCore DSO retains a build-host .interp.
                    if not p.startswith('usr/bin/'):
                        ignored_dso_interpreters.append(interp)
                        continue
                    found=resolve(interp)
                    assert found,(p,interp)
                    resolved['PT_INTERP']=found;todo.append(found)
            done[p]={'sha256':hashlib.sha256(data).hexdigest(),'dependencies':resolved,
                'unused_PT_INTERP_in_shared_library':ignored_dso_interpreters}
        return {'seeds':seeds,'elf_count':len(done),'missing':[],'files':done,
            'limit':'DT_NEEDED/interpreter existence and ARM machine type only; runtime imports, ioctl compatibility and hardware untested.'}
