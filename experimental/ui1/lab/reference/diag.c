#include "netcap.c"

/* Byte-counted stream spool; unlike dd count=N, short reads cannot rotate early.
 * Preserve the first 256 KiB, plus three recent 256 KiB segments. Files have
 * monotonically increasing names so USB copies preserve earlier segments.
 */
#define STREAM_LIMIT 262144u
static int stream_open(const char *dir,const char *name,unsigned seq,int initial) {
    char path[1024];
    int n=initial?snprintf(path,sizeof(path),"%s/%s.start.log",dir,name):
                  snprintf(path,sizeof(path),"%s/%s.%06u.log",dir,name,seq);
    if(n<0||n>=(int)sizeof(path)) {errno=ENAMETOOLONG;return -1;}
    return open(path,O_CREAT|O_TRUNC|O_WRONLY,0600);
}
static int stream_main(int argc,char **argv) {
    if(argc!=3||strlen(argv[1])>900||strlen(argv[2])>32)return 2;
    const char *dir=argv[1],*name=argv[2];
    if(strspn(name,"abcdefghijklmnopqrstuvwxyz0123456789-")!=strlen(name))return 2;
    int first=stream_open(dir,name,0,1),current=stream_open(dir,name,0,0);
    unsigned first_size=0,current_size=0,seq=0;
    char buf[8192];
    int failed=(first<0||current<0);
    if(failed)perror("R4 stream open failed; draining output");
    for(;;) {
        ssize_t n=read(0,buf,sizeof(buf));
        if(n<0&&errno==EINTR)continue;
        if(n<=0)break;
        if(failed)continue; /* Always drain the pipe, even after storage failure. */
        if(first>=0) {
            unsigned take=(unsigned)n;
            if(take>STREAM_LIMIT-first_size)take=STREAM_LIMIT-first_size;
            if(write_all(first,buf,take))failed=1;
            first_size+=take;
            if(first_size==STREAM_LIMIT) {close(first);first=-1;}
        }
        unsigned offset=0;
        while(offset<(unsigned)n&&!failed) {
            if(current_size==STREAM_LIMIT) {
                close(current);++seq;
                current=stream_open(dir,name,seq,0);current_size=0;
                if(current<0) {failed=1;break;}
                if(seq>=3) {
                    char old[1024];snprintf(old,sizeof(old),"%s/%s.%06u.log",dir,name,seq-3);
                    if(unlink(old)&&errno!=ENOENT) {failed=1;break;}
                }
            }
            unsigned take=(unsigned)n-offset;
            if(take>STREAM_LIMIT-current_size)take=STREAM_LIMIT-current_size;
            if(write_all(current,buf+offset,take)) {failed=1;break;}
            offset+=take;current_size+=take;
        }
        if(failed) {
            char status[1024];snprintf(status,sizeof(status),"%s/%s.error",dir,name);
            int fd=open(status,O_WRONLY|O_CREAT|O_TRUNC,0600);
            const char msg[]="Stream storage failed; output is being drained to avoid blocking the application.\n";
            if(fd>=0) {write_all(fd,msg,sizeof(msg)-1);close(fd);}
        }
    }
    if(first>=0)close(first);
    if(current>=0)close(current);
    return 0;
}
int main(int argc,char **argv) {
    if(argc==2&&!strcmp(argv[1],"--selftest")) {
        puts("P401 R4 diagnostic helper: ARM static build ready");return 0;
    }
    if(argc>=2&&!strcmp(argv[1],"stream"))return stream_main(argc-1,argv+1);
    if(argc>=2&&!strcmp(argv[1],"network"))return netcap_main(argc-1,argv+1);
    if(argc==5&&!strcmp(argv[1],"verify")) {
        int fd=open(argv[2],O_RDONLY);if(fd<0)return 1;
        uint32_t crc=0xffffffffu;unsigned long total=0;unsigned char buf[4096];
        for(;;) {
            ssize_t n=read(fd,buf,sizeof(buf));
            if(n<0&&errno==EINTR)continue;
            if(n<0) {close(fd);return 1;}if(!n)break;
            total+=(unsigned long)n;
            for(ssize_t i=0;i<n;++i) {
                crc^=buf[i];for(int bit=0;bit<8;++bit)crc=(crc>>1)^((0u-(crc&1u))&0xedb88320u);
            }
        }
        close(fd);crc^=0xffffffffu;
        return crc==(uint32_t)strtoul(argv[3],0,16)&&total==strtoul(argv[4],0,10)?0:1;
    }
    if(argc==4&&!strcmp(argv[1],"same")) {
        int a=open(argv[2],O_RDONLY),b=open(argv[3],O_RDONLY);
        if(a<0||b<0)return 1;
        unsigned char x[4096],y[4096];int rc=0;
        for(;;) {
            ssize_t na=read(a,x,sizeof(x)),nb=read(b,y,sizeof(y));
            if(na<0||nb<0||na!=nb||(na>0&&memcmp(x,y,(size_t)na))) {rc=1;break;}
            if(!na)break;
        }
        close(a);close(b);return rc;
    }
    fputs("usage: p401-diag --selftest | stream DIR NAME | network IFACE DIR SECONDS\n",stderr);
    return 2;
}
