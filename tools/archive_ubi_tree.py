"""Create an offline, metadata-preserving tar from a UBI image using ubi-reader.

Does not extract device nodes, execute firmware, or make a flashable image.
Binary xattrs are retained in the sidecar; this tool fails rather than silently
claim tar completeness if xattrs or sockets require additional handling.
"""
import argparse, base64, hashlib, io, json, pathlib, stat, struct, tarfile
from collections import Counter
from ubireader.ubi import ubi
from ubireader.ubifs import ubifs, walk
from ubireader.ubifs.misc import process_reg_file
from ubireader.ubifs.decrypt import decrypt_symlink_target
from ubireader.ubi_io import ubi_file, leb_virtual_file

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('image'); ap.add_argument('output'); ap.add_argument('--compare-tree')
    args=ap.parse_args()
    src=pathlib.Path(args.image); out=pathlib.Path(args.output); out.mkdir(parents=True, exist_ok=True)
    uf=ubi_file(str(src), 131072); u=ubi(uf)
    if len(u.images)!=1: raise ValueError('Expected one UBI image')
    img=u.images[0]
    for vn, vol in img.volumes.items():
        ub=ubifs(leb_virtual_file(u,vol.get_blocks(u.blocks)))
        inodes={}; bad=[]
        walk.index(ub,ub.master_node.root_lnum,ub.master_node.root_offs,inodes,bad)
        if bad: raise ValueError(f'Bad LEBs: {bad}')
        records=[]; seen={}; file_hashes={}; payloads={}
        def visit(ino,path,dent=None):
            node=inodes[ino]['ino']; item=inodes[ino]
            rec={'path':path, 'inode':ino, 'mode':node.mode,'uid':node.uid,'gid':node.gid,
                 'nlink':node.nlink,'size':node.size}
            for field in ['atime_sec','mtime_sec','ctime_sec','atime_nsec','mtime_nsec','ctime_nsec','flags','compr_type']:
                if hasattr(node,field):rec[field]=getattr(node,field)
            rec['xattrs']={x.name:base64.b64encode(inodes[x.inum]['ino'].data[:inodes[x.inum]['ino'].size]).decode('ascii') for x in item.get('xent',[])}
            kind=stat.S_IFMT(node.mode)
            rec['type']={stat.S_IFDIR:'directory',stat.S_IFREG:'file',stat.S_IFLNK:'symlink',stat.S_IFCHR:'char',stat.S_IFBLK:'block',stat.S_IFIFO:'fifo',stat.S_IFSOCK:'socket'}[kind]
            if kind==stat.S_IFLNK:
                rec['target']=decrypt_symlink_target(ub,inodes,dent)
            elif kind==stat.S_IFREG:
                if ino in seen:
                    rec['type']='hardlink';rec['target']=seen[ino]
                    rec['sha256']=file_hashes[ino]
                else:
                    data=process_reg_file(ub,item,path,inodes)
                    if len(data)!=node.size:raise ValueError('Size mismatch: '+path)
                    rec['sha256']=hashlib.sha256(data).hexdigest()
                    seen[ino]=path;file_hashes[ino]=rec['sha256'];payloads[path]=data
                if args.compare_tree:
                    disk=pathlib.Path(args.compare_tree)/path
                    if not disk.is_file() or hashlib.sha256(disk.read_bytes()).hexdigest()!=rec['sha256']:
                        raise ValueError('Prior extraction differs: '+path)
            elif kind in [stat.S_IFCHR,stat.S_IFBLK]:
                # UBIFS stores Linux new_encode_dev in a little-endian word.
                dev=struct.unpack('<I',node.data[:4])[0]
                rec['devmajor']=(dev>>8)&0xfff
                rec['devminor']=(dev&0xff)|((dev>>12)&0xfff00)
            records.append(rec)
            if kind==stat.S_IFDIR:
                for d in sorted(item.get('dent',[]),key=lambda d:d.name):
                    if d.name in ['.','..'] or '/' in d.name or '\\' in d.name or '\0' in d.name:raise ValueError('Invalid directory entry')
                    visit(d.inum,d.name if path=='.' else path+'/'+d.name,d)
        visit(1,'.')
        name=vn.decode() if isinstance(vn,bytes) else str(vn)
        meta={'source':str(src),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
              'volume':name,'image_seq':img.image_seq,'entries':records}
        (out/(name+'_metadata.json')).write_text(json.dumps(meta,indent=2),encoding='utf-8')
        if any(r['xattrs'] or r['type']=='socket' for r in records):raise ValueError('Metadata captured; tar requires xattr/socket handling')
        dest=out/(name+'_source_tree.tar')
        types={'directory':tarfile.DIRTYPE,'file':tarfile.REGTYPE,'symlink':tarfile.SYMTYPE,'hardlink':tarfile.LNKTYPE,'char':tarfile.CHRTYPE,'block':tarfile.BLKTYPE,'fifo':tarfile.FIFOTYPE}
        with tarfile.open(dest,'w',format=tarfile.PAX_FORMAT) as tf:
            for rec in records:
                t=tarfile.TarInfo(rec['path']);t.type=types[rec['type']];t.mode=stat.S_IMODE(rec['mode']);t.uid=rec['uid'];t.gid=rec['gid'];t.mtime=rec['mtime_sec']
                for key in ['atime','mtime','ctime']:
                    t.pax_headers[key]=str(rec[key+'_sec'])+'.'+str(rec.get(key+'_nsec',0)).zfill(9)
                if 'target' in rec:t.linkname=rec['target']
                if 'devmajor' in rec:t.devmajor=rec['devmajor'];t.devminor=rec['devminor']
                if rec['type']=='file':t.size=rec['size'];tf.addfile(t,io.BytesIO(payloads[rec['path']]))
                else:tf.addfile(t)
        with tarfile.open(dest,'r') as tf:
            members={m.name:m for m in tf.getmembers()}
            if len(members)!=len(records):raise ValueError('Tar member count mismatch')
            for rec in records:
                m=members[rec['path']]
                assert m.type==types[rec['type']] and m.uid==rec['uid'] and m.gid==rec['gid'] and m.mode==stat.S_IMODE(rec['mode'])
                for key in ['atime','mtime','ctime']:
                    assert m.pax_headers[key]==str(rec[key+'_sec'])+'.'+str(rec.get(key+'_nsec',0)).zfill(9)
                if 'target' in rec:assert m.linkname==rec['target']
                if 'devmajor' in rec:assert (m.devmajor,m.devminor)==(rec['devmajor'],rec['devminor'])
                if rec['type'] in ['file','hardlink']:
                    assert hashlib.sha256(tf.extractfile(m).read()).hexdigest()==rec['sha256']
        result={'archive':str(dest),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size,
                'types':dict(Counter(r['type'] for r in records)),'xattr_count':sum(len(r['xattrs']) for r in records),
                'verified_tar_entries':len(records),'prior_regular_files_compared':bool(args.compare_tree),'flashable':False,
                'ubifs_rebuild_completed':False}
        (out/(name+'_archive_validation.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))
    uf.close()

if __name__=='__main__':main()
