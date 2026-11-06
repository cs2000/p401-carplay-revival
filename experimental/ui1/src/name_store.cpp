#include "name_store.h"
#include <QtCore/qbytearray.h>
#include <QtCore/qfileinfo.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

namespace Revival {
bool laboratory() { const char *p=getenv("P401_UI_LAB"); return p && !strcmp(p,"1"); }
bool namesAvailable() { const char *p=getenv("P401_UI_NAMES");return laboratory()||(p&&!strcmp(p,"1")); }
static const char *directory() { return laboratory()?"/lab/control":"/data/carplay-revival"; }
static QString filePath() { return QString::fromLatin1(directory())+"/network-name"; }
bool validName(const QString &name) {
    if(name.isEmpty() || name.size()>24 || name.trimmed()!=name) return false;
    for(int i=0;i<name.size();++i) {
        unsigned c=name.at(i).unicode();
        if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c==' '||c=='-'||c=='_')) return false;
    }
    return true;
}
QString savedName() {
    char b[27]={0}; QByteArray p=filePath().toLocal8Bit();
    QFileInfo info(filePath());if(!info.isFile()||info.isSymLink()||info.size()>25)return QString();
    int fd=open(p.constData(),O_RDONLY|O_NOFOLLOW); if(fd<0) return QString();
    ssize_t n=read(fd,b,sizeof(b)-1); close(fd);
    if(n<=0) return QString();
    if(b[n-1]=='\n') --n;
    QString v=QString::fromLatin1(b,int(n)); return validName(v)?v:QString();
}
bool saveName(const QString &input, QString &error) {
    QString name=input.trimmed();
    if(!validName(name)) { error=QString::fromUtf8("Use 1–24 letters, numbers, spaces, - or _.");return false; }
    if(mkdir(directory(),0755) && errno!=EEXIST) { error="Could not open the saved settings folder.";return false; }
    QFileInfo folder(QString::fromLatin1(directory()));
    if(!folder.isDir()||folder.isSymLink()) { error="Saved settings folder is unavailable.";return false; }
    QByteArray target=filePath().toLocal8Bit();
    // mkstemp uses an exclusive random filename, so an interrupted write cannot
    // block the next save or make us follow a pre-existing symlink.
    QByteArray temp=(filePath()+".XXXXXX").toLocal8Bit();
    QByteArray bytes=name.toLatin1()+"\n";
    int fd=mkstemp(temp.data());
    if(fd<0) { error="Could not start saving. Your current name is unchanged.";return false; }
    int done=0;bool ok=true;
    while(done<bytes.size()) {ssize_t n=write(fd,bytes.constData()+done,bytes.size()-done);if(n<0&&errno==EINTR)continue;if(n<=0){ok=false;break;}done+=n;}
    if(ok) ok=fsync(fd)==0;
    if(close(fd)) ok=false;
    if(!ok) { unlink(temp.constData());error="Could not save. Your current name is unchanged.";return false; }
    if(rename(temp.constData(),target.constData())) { unlink(temp.constData());error="Could not replace the saved name.";return false; }
    int d=open(directory(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
    ok=d>=0 && fsync(d)==0; if(d>=0)close(d);
    if(!ok) { error="Name saved, but storage did not confirm it. Restart has been cancelled.";return false; }
    return true;
}
}
