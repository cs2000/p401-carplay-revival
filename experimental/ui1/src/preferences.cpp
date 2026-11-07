#include "preferences.h"
#include "name_store.h"
#include <QtCore/qbytearray.h>
#include <QtCore/qfileinfo.h>
#include <QtCore/qlist.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>

namespace Revival {
static const char *directory() { return laboratory()?"/lab/control":"/data/carplay-revival"; }
static QString filePath() { return QString::fromLatin1(directory())+"/appearance"; }

AppearancePreferences defaultAppearancePreferences() {
    AppearancePreferences value;value.accent=0;
    for(int i=0;i<6;++i){value.order[i]=i;value.pictures[i]=i;}
    return value;
}
bool validAppearancePreferences(const AppearancePreferences &value) {
    if(value.accent<0||value.accent>=6)return false;
    int seen=0;
    for(int i=0;i<6;++i) {
        if(value.order[i]<0||value.order[i]>=6||value.pictures[i]<0||value.pictures[i]>=6)return false;
        if(seen&(1<<value.order[i]))return false;
        seen|=1<<value.order[i];
    }
    return seen==63;
}
static bool sixIndices(const QByteArray &line,const char *prefix,int result[6]) {
    QByteArray start(prefix);
    if(!line.startsWith(start)||line.size()!=start.size()+11)return false;
    for(int i=0;i<6;++i) {
        char c=line.at(start.size()+i*2);
        if(c<'0'||c>'5'||(i<5&&line.at(start.size()+i*2+1)!=','))return false;
        result[i]=c-'0';
    }
    return true;
}
static bool decode(const QByteArray &bytes,AppearancePreferences &result) {
    // One small, versioned, canonical ASCII record. Never partially apply a
    // damaged preference file or accept duplicate/order/factory-setting keys.
    QList<QByteArray> lines=bytes.split('\n');
    if(lines.size()!=5||lines.at(0)!="P401-APPEARANCE-1"||!lines.at(4).isEmpty())return false;
    if(lines.at(1).size()!=8||!lines.at(1).startsWith("accent=")||lines.at(1).at(7)<'0'||lines.at(1).at(7)>'5')return false;
    AppearancePreferences value;value.accent=lines.at(1).at(7)-'0';
    if(!sixIndices(lines.at(2),"order=",value.order)||!sixIndices(lines.at(3),"pictures=",value.pictures)||!validAppearancePreferences(value))return false;
    result=value;return true;
}
static QByteArray encode(const AppearancePreferences &value) {
    QByteArray bytes("P401-APPEARANCE-1\naccent=");bytes+=char('0'+value.accent);bytes+="\norder=";
    for(int i=0;i<6;++i){if(i)bytes+=',';bytes+=char('0'+value.order[i]);}
    bytes+="\npictures=";
    for(int i=0;i<6;++i){if(i)bytes+=',';bytes+=char('0'+value.pictures[i]);}
    return bytes+'\n';
}
static AppearancePreferences load() {
    AppearancePreferences value=defaultAppearancePreferences();
    QFileInfo folder(QString::fromLatin1(directory()));
    if(!folder.isDir()||folder.isSymLink())return value;
    QFileInfo info(filePath());
    if(!info.isFile()||info.isSymLink()||info.size()>128)return value;
    QByteArray path=filePath().toLocal8Bit();
    int fd=open(path.constData(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK);if(fd<0)return value;
    char buffer[129];int done=0;bool ok=true;
    while(done<int(sizeof(buffer))) {
        ssize_t n=read(fd,buffer+done,sizeof(buffer)-done);
        if(n<0&&errno==EINTR)continue;
        if(n<0){ok=false;break;}if(!n)break;done+=int(n);
    }
    close(fd);
    AppearancePreferences parsed;
    if(ok&&done<129&&decode(QByteArray(buffer,done),parsed))value=parsed;
    return value;
}
static AppearancePreferences &current() {static AppearancePreferences value=load();return value;}
static unsigned revision=1;
AppearancePreferences appearancePreferences() {return current();}
unsigned preferencesRevision() {current();return revision;}
QColor appearanceAccent(int index) {
    switch(index) {
    case 1:return QColor(117,180,239); // Sapphire
    case 2:return QColor(222,179,113); // Champagne
    case 3:return QColor(134,204,157); // Emerald
    case 4:return QColor(190,157,226); // Amethyst
    case 5:return QColor(223,226,230); // Glacier
    default:return QColor(95,205,199); // Original approved turquoise
    }
}
QString appearanceAccentName(int index) {
    static const char *names[]={"Turquoise","Sapphire","Champagne","Emerald","Amethyst","Glacier"};
    return QString::fromLatin1(names[index>=0&&index<6?index:0]);
}
QColor accentColor(){return appearanceAccent(current().accent);}
int tileOrderRank(int kind) {
    if(kind<0||kind>=6)return kind;
    const AppearancePreferences &value=current();
    for(int i=0;i<6;++i)if(value.order[i]==kind)return i;
    return kind;
}
int tilePictureIndex(int kind){return kind>=0&&kind<6?current().pictures[kind]:kind;}
bool saveAppearancePreferences(const AppearancePreferences &value,QString &error) {
    error.clear();
    if(!validAppearancePreferences(value)){error="Choose valid colours, pictures and a complete tile order.";return false;}
    // A non-symlink data directory and exclusive temporary file prevent saves
    // from following an existing file link. Factory/MCU profiles are untouched.
    if(mkdir(directory(),0755)&&errno!=EEXIST){error="Could not open the saved settings folder.";return false;}
    QFileInfo folder(QString::fromLatin1(directory()));
    if(!folder.isDir()||folder.isSymLink()){error="Saved settings folder is unavailable.";return false;}
    QByteArray target=filePath().toLocal8Bit(),temp=(filePath()+".XXXXXX").toLocal8Bit(),bytes=encode(value);
    int fd=mkstemp(temp.data());
    if(fd<0){error="Could not start saving. Your appearance is unchanged.";return false;}
    // mkstemp guarantees 0600, including when the process has a permissive umask.
    int done=0;bool ok=true;
    while(done<bytes.size()) {
        ssize_t n=write(fd,bytes.constData()+done,bytes.size()-done);
        if(n<0&&errno==EINTR)continue;if(n<=0){ok=false;break;}done+=int(n);
    }
    if(ok)ok=fsync(fd)==0;if(close(fd))ok=false;
    if(!ok){unlink(temp.constData());error="Could not save. Your appearance is unchanged.";return false;}
    if(rename(temp.constData(),target.constData())){unlink(temp.constData());error="Could not replace the saved appearance.";return false;}
    current()=value;++revision;
    int d=open(directory(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW);ok=d>=0&&fsync(d)==0;if(d>=0)close(d);
    if(!ok){error="Appearance applied, but storage did not confirm it. Please try saving again.";return false;}
    return true;
}
}
