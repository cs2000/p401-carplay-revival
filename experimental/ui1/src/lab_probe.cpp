// Isolated simulator checks. Never runs without P401_UI_LAB=1 and a lab request.
#include "name_store.h"
#include <QtGui/qapplication.h>
#include <QtGui/qlistview.h>
#include <QtCore/qfile.h>
#include <QtCore/qvariant.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern "C" void *vendor_dlsym(void *,const char *) __asm__("dlsym");
#define dlsym vendor_dlsym
extern "C" void ini_value(void*,const QString&,const QVariant&);
extern "C" void app_tag(void*,unsigned,QVariant);
void runLabProbe() {
    if(!Revival::laboratory()||!QFile::exists("/lab/control/probe.request"))return;
    QFile::remove("/lab/control/probe.request");
    FILE *out=fopen("/lab/control/probe-results.txt","w");if(!out)return;
    fprintf(out,"saved_name=%s\n",Revival::savedName().toUtf8().constData());fflush(out);
    fprintf(out,"child_preload=%s\n",getenv("LD_PRELOAD")?getenv("LD_PRELOAD"):"unset");
    bool names_ok=Revival::validName("A")&&Revival::validName("Jaguar-XFR_123")&&Revival::validName("ABCDEFGHIJKLMNOPQRSTUVWX")
        &&!Revival::validName("")&&!Revival::validName("ABCDEFGHIJKLMNOPQRSTUVWXY")&&!Revival::validName(" trailing ")
        &&!Revival::validName("line\nbreak")&&!Revival::validName("$(echo x)")&&!Revival::validName(QString::fromUtf8("Jaguár"));
    fprintf(out,"name_validation=%s\n",names_ok?"PASS":"FAIL");
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
    typedef int(*CurrentApp)(void*);CurrentApp currentApp=(CurrentApp)dlsym(common,"_ZN14MsnApplication13getCurModeAppEv");
    fprintf(out,"current_mode_app=%d\n",currentApp?currentApp(qApp):-1);
    Set set=(Set)dlsym(RTLD_DEFAULT,"_ZN12MsnIniConfig8setValueERK7QStringRK8QVariant");
    Tag tag=(Tag)dlsym(RTLD_DEFAULT,"_ZN14MsnApplication6setTagE8AppTagId8QVariant");
    if(ctor&&dtor&&value&&getTag&&set&&tag) {
        unsigned storage[256]={0};ctor(storage,QString("/etc/hostapd/hostapd.conf"));
        set(storage,QString("ssid"),QVariant("carplay_test"));
        set(storage,QString("channel"),QVariant(6));
        fprintf(out,"hostapd_ssid=%s\n",value(storage,"ssid",QVariant()).toString().toUtf8().constData());
        fprintf(out,"other_key=%d\n",value(storage,"channel",QVariant()).toInt());
        dtor(storage);ctor(storage,QString("/tmp/revival-unrelated.ini"));
        set(storage,QString("ssid"),QVariant("Unrelated network"));
        fprintf(out,"unrelated_ssid=%s\n",value(storage,"ssid",QVariant()).toString().toUtf8().constData());dtor(storage);
        tag(qApp,0x11017,QVariant("carplay_test"));
        fprintf(out,"advertised_ssid=%s\n",getTag(qApp,0x11017,QVariant()).toString().toUtf8().constData());
    }else fprintf(out,"ERROR=missing native configuration symbols\n");
    fflush(out);
    QWidgetList widgets=QApplication::allWidgets();
    QString visibleApps;
    for(int i=0;i<widgets.size();++i) {
        QWidget *w=widgets[i];
        if(w->isVisible()&&w->inherits("MsnMainWindow")) {
            typedef unsigned(*AppId)(void*);AppId id=(AppId)dlsym(common,"_ZN13MsnMainWindow8getAppIdEv");
            if(id){if(!visibleApps.isEmpty())visibleApps+=",";visibleApps+=QString::number(id(w));}
        }
        if(w->objectName()=="listviewMain") {
            QListView *v=qobject_cast<QListView*>(w);
            if(v&&v->model())for(int j=0;j<v->model()->rowCount();++j){QModelIndex ix=v->model()->index(j,0);fprintf(out,"app=%d,%s\n",v->model()->data(ix,35).toInt(),v->model()->data(ix).toString().toUtf8().constData());}
        }
        if(!strcmp(w->metaObject()->className(),"BtSettingPanel")) {
            void *lib=dlopen("/usr/lib/libBlueTooth.so",RTLD_NOW|RTLD_NOLOAD);
            typedef void(*Recv)(void*,QString);Recv recv=(Recv)dlsym(lib,"_ZN14BtSettingPanel16onRecvDeviceNameE7QString");
            fprintf(out,"bt_panel=found,adapter=%p\n",*(void**)((char*)w+0x80));fflush(out);
            if(recv&&*(void**)((char*)w+0x80)) {
                recv(w,QString("LAB factory name"));
                fprintf(out,"bluetooth_desired=%s\n",((QString*)((char*)w+0x24))->toUtf8().constData());
            }
            if(lib)dlclose(lib);
        }
    }
    fprintf(out,"visible_apps=%s\n",visibleApps.toUtf8().constData());
    typedef int(*Lock)();Lock lock=(Lock)dlsym(RTLD_DEFAULT,"_Z24GetRebootSystemLockCountv");
    fprintf(out,"native_restart_lock=%s\n",lock?"available":"MISSING");
    if(common)dlclose(common);fclose(out);
}
