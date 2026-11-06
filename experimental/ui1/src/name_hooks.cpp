// Keep the SSID advertised to the phone identical to the AP configuration.
// The Bluetooth suffix hook is restricted to the inspected V3.22.1 callsite.
#include "name_store.h"
#include <QtCore/qvariant.h>
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
extern "C" void *vendor_dlsym(void *,const char *) __asm__("dlsym");
#define dlsym vendor_dlsym

static const QString &activeName() {
    // A save takes effect on the next process startup, not midway through pairing.
    static __thread bool loading=false;
    static const QString empty;
    if(!Revival::namesAvailable())return empty;
    if(loading)return empty;
    loading=true;
    static const QString name=Revival::savedName();
    loading=false;return name;
}
extern "C" QString &append_name(QString *,const QString &) __asm__("_ZN7QString6appendERKS_");
extern "C" QString &append_name(QString *self,const QString &other) {
    typedef QString&(*Fn)(QString*,const QString&);
    static Fn original=(Fn)dlsym(RTLD_NEXT,"_ZN7QString6appendERKS_");
    if(!activeName().isEmpty()) {
        void *caller=__builtin_return_address(0);Dl_info info;
        if(dladdr(caller,&info)&&info.dli_sname&&
           !strcmp(info.dli_sname,"_ZN14BtSettingPanel16onRecvDeviceNameE7QString")&&
           (uintptr_t)caller-(uintptr_t)info.dli_saddr==0x2a0) {
            const uint32_t *site=(const uint32_t *)((const char *)info.dli_saddr+0x298);
            if(site[0]==0xe1a01006&&site[1]==0xebffae02) {*self=activeName();return *self;}
        }
    }
    return original(self,other);
}
extern "C" void ini_value(void *,const QString &,const QVariant &) __asm__("_ZN12MsnIniConfig8setValueERK7QStringRK8QVariant");
extern "C" void ini_value(void *self,const QString &key,const QVariant &value) {
    typedef void(*Fn)(void*,const QString&,const QVariant&);
    typedef QString(*Filename)(void*);
    static Fn original=(Fn)dlsym(RTLD_NEXT,"_ZN12MsnIniConfig8setValueERK7QStringRK8QVariant");
    static Filename filename=(Filename)dlsym(RTLD_NEXT,"_ZN12MsnIniConfig8fileNameEv");
    if(!original)return;
    if(key=="ssid"&&!activeName().isEmpty()&&filename) {
        QString file=filename(self);
        if(file=="/etc/hostapd/hostapd.conf"||file=="/tmp/hostapd.conf") {
            original(self,key,QVariant(activeName()));return;
        }
    }
    original(self,key,value);
}
extern "C" void app_tag(void *,unsigned,QVariant) __asm__("_ZN14MsnApplication6setTagE8AppTagId8QVariant");
extern "C" void app_tag(void *self,unsigned tag,QVariant value) {
    typedef void(*Fn)(void*,unsigned,QVariant);
    static Fn original=(Fn)dlsym(RTLD_NEXT,"_ZN14MsnApplication6setTagE8AppTagId8QVariant");
    const QString &name=activeName();
    if(original)original(self,tag,tag==0x11017&&!name.isEmpty()?QVariant(name):value);
}
