// Test-only storage probe. It loads the production preference source unchanged
// in the matching ARM Qt process; no probe code is shipped in the UI library.
#include "preferences.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
namespace Revival {bool laboratory(){return true;}}
static void dump(const char *prefix) {
    Revival::AppearancePreferences value=Revival::appearancePreferences();
    printf("%s accent=%d order=",prefix,value.accent);
    for(int i=0;i<6;++i)printf("%s%d",i?",":"",value.order[i]);
    printf(" pictures=");for(int i=0;i<6;++i)printf("%s%d",i?",":"",value.pictures[i]);
    printf(" revision=%u ranks=",Revival::preferencesRevision());
    for(int i=0;i<6;++i)printf("%s%d",i?",":"",Revival::tileOrderRank(i));
    printf("\n");
}
__attribute__((constructor)) static void preferenceProbe() {
    dump("loaded");
    const char *action=getenv("P401_PREFERENCE_TEST_ACTION");
    if(action&&*action) {
        Revival::AppearancePreferences value=Revival::defaultAppearancePreferences();
        if(!strcmp(action,"custom")) {
            value.accent=3;
            for(int i=0;i<6;++i){value.order[i]=5-i;value.pictures[i]=(i+2)%6;}
        } else if(!strcmp(action,"invalid-order"))value.order[5]=0;
        else if(!strcmp(action,"invalid-accent"))value.accent=6;
        else if(!strcmp(action,"invalid-picture"))value.pictures[0]=6;
        QString error;bool ok=Revival::saveAppearancePreferences(value,error);
        printf("saved=%d error=%s\n",ok?1:0,error.toUtf8().constData());dump("after");
    }
    fflush(stdout);
}
