// Observe the licensed native stack; do not probe radios or start services.
//
// V3.22.1 evidence (matching carplay executable retains DWARF enum names):
//   CARPLAY=0, CARPLAY_WIRELESS=7; LINK_SUCCESS=4.
//   CarplayDbus::linkstatus_callback_func, 0x1b474..0x1b4c0, maps
//   CMD_SUCCESS=15 to LINK_SUCCESS=4. CMD_STARTING=23 -> 3,
//   CMD_REMOVED=14 -> 8, CMD_FAILED=16 -> 5, CMD_NOTINSERTED=19 -> 10.
//   CarPlayWindow::updateLinkStatus, 0x90f0, marks the session connected only
//   on 4; 0x8ef4 clears it on 5/8/10. Bluetooth/Wi-Fi availability and the
//   transport's LINK_CONNECTED=1 are not proof of a working CarPlay session.
//
// MsnLink is a direct MsnCoreApp dependency. Its native status handler forwards
// through the signal PLT from startup, independently of CarPlayWindow lifetime.
// Service loss emits failure 5 for both CarPlay types (0x8174..0x8190).
// RC2 compatibility.txt additionally pins the complete libLinkLibs.so:
// length 129180, CRC32 59ed7170,
// SHA256 ac7d73df4bdd7dfa59e4042dbf46c19797eb3ce84cca630dff79308911e8acdc.
#include "connection_status.h"
#include <QtCore/qatomic.h>
#include <dlfcn.h>
#include <stdint.h>
#include <string.h>

extern "C" void *vendor_dlsym(void *,const char *) __asm__("dlsym");
#define dlsym vendor_dlsym

namespace {
// 0=waiting, 1=wired session, 8=wireless session. One atomic value keeps the
// transport and visible state together; a stale USB removal cannot clear Wi-Fi.
QBasicAtomicInt session=Q_BASIC_ATOMIC_INITIALIZER(0);
QBasicAtomicInt revision=Q_BASIC_ATOMIC_INITIALIZER(0);

typedef void(*LinkSignal)(void *,int,int);
const char signalName[]="_ZN7MsnLink18onLinkStatusChangeEii";

bool matchingSignal(LinkSignal signal) {
    if(!signal)return false;
    Dl_info info;
    if(!dladdr((void *)signal,&info)||!info.dli_fname||!info.dli_sname||
       strcmp(info.dli_sname,signalName)||info.dli_saddr!=(void *)signal||
       (uintptr_t)signal-(uintptr_t)info.dli_fbase!=0x16f28)return false;
    const char *file=strrchr(info.dli_fname,'/');
    if(strcmp(file?file+1:info.dli_fname,"libLinkLibs.so"))return false;
    const uint32_t *entry=(const uint32_t *)(void *)signal;
    // Exact ARM entry of the two-int Qt signal, not a guessed QObject layout.
    return entry[0]==0xe52de004&&entry[1]==0xe59fe03c&&
           entry[2]==0xe24dd01c&&entry[3]==0xe3a0c000;
}

void observe(int type,int status) {
    if(type!=0&&type!=7)return;
    const int old=session.fetchAndAddOrdered(0);
    int next=old;
    if(status==4)next=type+1;
    else if(old==type+1&&
            (status==2||status==3||status==5||status==7||status==8||
             status==10||status==24||status==255||status<0))next=0;
    // LINK_EXITING=6 is also the native CMD_BACKGROUND notification. Calls,
    // Siri, music and display state notifications do not end the session.
    if(next!=old&&session.testAndSetOrdered(old,next)) {
        if((old!=0)!=(next!=0))revision.fetchAndAddOrdered(1);
    }
}
}

namespace Revival {
bool carPlayConnected(){return session.fetchAndAddOrdered(0)!=0;}
unsigned carPlayStatusRevision(){return (unsigned)revision.fetchAndAddOrdered(0);}
QString carPlayStatusText(){return QString::fromLatin1(carPlayConnected()?"Connected":"Waiting for phone");}
}

extern "C" void revival_link_status(void *,int,int) __asm__("_ZN7MsnLink18onLinkStatusChangeEii");
extern "C" void revival_link_status(void *self,int type,int status) {
    static LinkSignal original=(LinkSignal)dlsym(RTLD_NEXT,signalName);
    static const bool supported=matchingSignal(original);
    if(supported)observe(type,status);
    // Preserve every original signal and payload, including unsupported types.
    if(original)original(self,type,status);
}
