// Separate test-only observations of production naming endpoints.
// No P401_UI_LAB override, radio, MCU or reboot replacement is used.
#include <QtGui/qapplication.h>
#include <QtGui/qwidget.h>
#include <QtCore/qvariant.h>
#include <QtCore/qfile.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
extern "C" void *vendor_dlsym(void *,const char *) __asm__("dlsym");
#define dlsym vendor_dlsym
void settingsProbe(FILE *out) {
    fprintf(out,"child_preload=%s\n",getenv("LD_PRELOAD")?getenv("LD_PRELOAD"):"unset");
    void *common=dlopen("/usr/lib/libMsnCommons.so",RTLD_NOW|RTLD_NOLOAD);
    typedef void(*Ctor)(void*,const QString&);typedef void(*Dtor)(void*);
    typedef QVariant(*Value)(void*,const QString&,const QVariant&);
    typedef QVariant(*GetTag)(void*,unsigned,QVariant);
    typedef void(*Set)(void*,const QString&,const QVariant&);
    typedef void(*Tag)(void*,unsigned,QVariant);
    Ctor ctor=(Ctor)dlsym(common,"_ZN12MsnIniConfigC1ERK7QString");
    Dtor dtor=(Dtor)dlsym(common,"_ZN12MsnIniConfigD1Ev");
    Value value=(Value)dlsym(common,"_ZN12MsnIniConfig5valueERK7QStringRK8QVariant");
    GetTag getTag=(GetTag)dlsym(common,"_ZN14MsnApplication6getTagE8AppTagId8QVariant");
    Set set=(Set)dlsym(RTLD_DEFAULT,"_ZN12MsnIniConfig8setValueERK7QStringRK8QVariant");
    Tag tag=(Tag)dlsym(RTLD_DEFAULT,"_ZN14MsnApplication6setTagE8AppTagId8QVariant");
    if(ctor&&dtor&&value&&getTag&&set&&tag) {
        unsigned storage[256]={0};ctor(storage,QString("/tmp/hostapd.conf"));
        set(storage,QString("ssid"),QVariant("CLOUD-default"));
        set(storage,QString("channel"),QVariant(6));
        fprintf(out,"hostapd_ssid=%s\n",value(storage,"ssid",QVariant()).toString().toUtf8().constData());
        fprintf(out,"other_key=%d\n",value(storage,"channel",QVariant()).toInt());
        dtor(storage);ctor(storage,QString("/tmp/cloud-unrelated.ini"));
        set(storage,QString("ssid"),QVariant("Unrelated network"));
        fprintf(out,"unrelated_ssid=%s\n",value(storage,"ssid",QVariant()).toString().toUtf8().constData());dtor(storage);
        tag(qApp,0x11017,QVariant("CLOUD-default"));
        fprintf(out,"advertised_ssid=%s\n",getTag(qApp,0x11017,QVariant()).toString().toUtf8().constData());
    } else fprintf(out,"endpoint_error=missing native config symbols\n");
    QWidgetList widgets=QApplication::allWidgets();
    for(int i=0;i<widgets.size();++i) {
        QWidget *w=widgets[i];
        if(!strcmp(w->metaObject()->className(),"BtSettingPanel")) {
            void *lib=dlopen("/usr/lib/libBlueTooth.so",RTLD_NOW|RTLD_NOLOAD);
            typedef void(*Recv)(void*,QString);Recv recv=(Recv)dlsym(lib,"_ZN14BtSettingPanel16onRecvDeviceNameE7QString");
            if(recv&&*(void**)((char*)w+0x80)) {
                recv(w,QString("CLOUD factory name"));
                fprintf(out,"bluetooth_desired=%s\n",((QString*)((char*)w+0x24))->toUtf8().constData());
            }
            if(lib)dlclose(lib);
        }
    }
    typedef int(*Lock)();Lock lock=(Lock)dlsym(RTLD_DEFAULT,"_Z24GetRebootSystemLockCountv");
    fprintf(out,"native_restart_lock=%d\n",lock?lock():-1);
    if(common)dlclose(common);
}

// Observe and forward the vendor's reboot request. The isolated container has
// no CAP_SYS_BOOT, UART or MCU; this establishes dispatch, never hardware reboot.
extern "C" void observe_reboot() __asm__("_Z19RequestRebootSystemv");
extern "C" void observe_reboot() {
    FILE *marker=fopen("/lab/control/native-restart.requested","w");
    if(marker){fputs("native RequestRebootSystem reached\n",marker);fclose(marker);}
    fprintf(stderr,"CLOUD PROBE: native restart requested\n");
    typedef void(*Request)();static Request real=(Request)dlsym(RTLD_NEXT,"_Z19RequestRebootSystemv");
    if(real)real();
}

// Force only the native busy-lock response in one explicit fixture. Otherwise
// forward the real lock query unchanged; production binary has no test branch.
extern "C" int observe_lock() __asm__("_Z24GetRebootSystemLockCountv");
extern "C" int observe_lock() {
    if(access("/lab/control/force-reboot-lock",F_OK)==0)return 1;
    typedef int(*Lock)();static Lock real=(Lock)dlsym(RTLD_NEXT,"_Z24GetRebootSystemLockCountv");
    return real?real():1;
}
