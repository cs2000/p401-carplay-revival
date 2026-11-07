// Separate RC2-only observer. Native input and vendor handlers remain intact.
// No laboratory production override, physical device or factory writes.
#include <QtGui/qapplication.h>
#include <QtGui/qabstractbutton.h>
#include <QtGui/qcombobox.h>
#include <QtGui/qlabel.h>
#include <QtGui/qtabwidget.h>
#include <QtGui/qtabbar.h>
#include <QtGui/qcolor.h>
#include <QtGui/qpixmap.h>
#include <QtGui/qlistview.h>
#include <QtGui/qabstractitemdelegate.h>
#include <QtCore/qfile.h>
#include <QtCore/qvariant.h>
#include <QtCore/qregexp.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
extern "C" void *vendor_dlsym(void *,const char *) __asm__("dlsym");
#define dlsym vendor_dlsym

static QByteArray safeText(QString value) {
    value.replace('\n'," ");value.replace('\r'," ");value.replace('|',"/");
    return value.toUtf8();
}

void rc2Probe(FILE *out,const QByteArray &action) {
    if(action=="advanced-native-metacall") {
        bool invoked=false;QWidgetList all=QApplication::allWidgets();
        for(int i=0;i<all.size();++i)if(!strcmp(all[i]->metaObject()->className(),"FactoryWindow")&&all[i]->isVisible())
            invoked=QMetaObject::invokeMethod(all[i],"on_btnAdminSetting_clicked",Qt::DirectConnection);
        fprintf(out,"rc2_advanced_metacall=%d\n",invoked);
    }
    if(action=="bluetooth-ready-tags") {
        typedef void(*SetTag)(void*,unsigned,QVariant);
        SetTag set=(SetTag)dlsym(RTLD_DEFAULT,"_ZN14MsnApplication6setTagE8AppTagId8QVariant");
        if(set){set(qApp,0x10001,QVariant(unsigned(0x800000)));set(qApp,0x1100c,QVariant(unsigned(1)));}
        fprintf(out,"rc2_bluetooth_ready_tags_dispatched=%d\n",bool(set));
    }
    if(action.startsWith("link:")) {
        QList<QByteArray> fields=action.split(':');bool a=false,b=false;
        int type=fields.size()==3?fields[1].toInt(&a):0,status=fields.size()==3?fields[2].toInt(&b):0;
        void *lib=dlopen("/usr/lib/libLinkLibs.so",RTLD_NOW|RTLD_NOLOAD);
        void **link=lib?(void**)dlsym(lib,"gLink"):0;
        typedef void(*NativeStatus)(void*,int,int);
        NativeStatus change=lib?(NativeStatus)dlsym(lib,"_ZN7MsnLink24onLinkStatusChangeNativeEii"):0;
        bool called=a&&b&&link&&*link&&change;
        if(called)change(*link,type,status);
        fprintf(out,"rc2_native_link_dispatched=%d\n",called);
        if(lib)dlclose(lib);
    }
    // Functions are resolved from the actual loaded production library. Missing
    // feature symbols are a failed assertion in the Python validator.
    typedef QColor(*Accent)();typedef int(*Index)(int);typedef unsigned(*Revision)();
    Accent accent=(Accent)dlsym(RTLD_DEFAULT,"_ZN7Revival11accentColorEv");
    Index rank=(Index)dlsym(RTLD_DEFAULT,"_ZN7Revival13tileOrderRankEi");
    Index picture=(Index)dlsym(RTLD_DEFAULT,"_ZN7Revival16tilePictureIndexEi");
    Revision revision=(Revision)dlsym(RTLD_DEFAULT,"_ZN7Revival19preferencesRevisionEv");
    fprintf(out,"rc2_preferences_symbols=%d\n",bool(accent&&rank&&picture&&revision));
    if(accent&&rank&&picture&&revision) {
        fprintf(out,"rc2_accent=%s\nrc2_preferences_revision=%u\n",accent().name().toUtf8().constData(),revision());
        for(int i=0;i<6;++i)fprintf(out,"rc2_tile=%d,%d,%d\n",i,rank(i),picture(i));
    }
    typedef bool(*Connected)();typedef QString(*StatusText)();
    Connected connected=(Connected)dlsym(RTLD_DEFAULT,"_ZN7Revival16carPlayConnectedEv");
    StatusText statusText=(StatusText)dlsym(RTLD_DEFAULT,"_ZN7Revival17carPlayStatusTextEv");
    Revision statusRevision=(Revision)dlsym(RTLD_DEFAULT,"_ZN7Revival21carPlayStatusRevisionEv");
    fprintf(out,"rc2_connection_symbols=%d\n",bool(connected&&statusText&&statusRevision));
    if(connected&&statusText&&statusRevision)fprintf(out,"rc2_connected=%d\nrc2_status=%s\nrc2_status_revision=%u\n",connected(),statusText().toUtf8().constData(),statusRevision());
    QWidgetList widgets=QApplication::allWidgets();
    for(int i=0;i<widgets.size();++i) {
        QWidget *w=widgets[i];if(!w->isVisible())continue;
        if(w->objectName()=="chkTabSel"||qobject_cast<QTabWidget*>(w)) {
            QString sheet=w->styleSheet();
            fprintf(out,"rc2_local_style=%s|%s|%s\n",w->metaObject()->className(),w->objectName().toUtf8().constData(),safeText(sheet).constData());
            QRegExp url("url\\(([^)]+)\\)");int offset=0;
            while((offset=url.indexIn(sheet,offset))>=0) {
                QString path=url.cap(1).trimmed();path.remove('"');path.remove('\'');QPixmap resource(path);
                fprintf(out,"rc2_style_resource=%s|%s|%d,%d\n",w->objectName().toUtf8().constData(),safeText(path).constData(),resource.width(),resource.height());offset+=url.matchedLength();
            }
        }
        if(!strcmp(w->metaObject()->className(),"SettingWindow")||!strcmp(w->metaObject()->className(),"FactoryWindow"))
            fprintf(out,"rc2_settings_theme=%s|%d|%u\n",w->metaObject()->className(),w->property("RevivalSettingsTheme").isValid(),w->property("RevivalSettingsTheme").toUInt());
        if(!strcmp(w->metaObject()->className(),"FactoryWindow")) {
            const char *slot="_ZN13FactoryWindow26on_btnAdminSetting_clickedEv";
            void *lib=dlopen("/usr/lib/libSetting.so",RTLD_NOW|RTLD_NOLOAD),*native=lib?dlsym(lib,slot):0,*hook=dlsym(RTLD_DEFAULT,slot);
            static const uint32_t expected[]={0xe5903050,0xe3a01000,0xe593000c,0xeafef5a6};
            fprintf(out,"rc2_advanced_slot=%d|%d|%d\n",bool(native),native&&hook&&native!=hook,native&&!memcmp(native,expected,sizeof(expected)));
            if(lib)dlclose(lib);
            void *common=dlopen("/usr/lib/libMsnCommons.so",RTLD_NOW|RTLD_NOLOAD);
            typedef QString(*McuVersion)();
            McuVersion version=common?(McuVersion)dlsym(common,"_Z17GetMCUVersion_MSNv"):0;
            QLabel *label=w->findChild<QLabel*>("labMCUVersion");
            if(version&&label) {
                QString value=version();
                fprintf(out,"rc2_mcu_version_label=%d|%d|%s\n",label->isVisible(),label->text()==value,safeText(label->text()).constData());
            }
            if(common)dlclose(common);
        }
        QPoint p=w->mapToGlobal(QPoint());QByteArray text;
        if(QAbstractButton *b=qobject_cast<QAbstractButton*>(w))text=safeText(b->text());
        else if(QLabel *label=qobject_cast<QLabel*>(w))text=safeText(label->text());
        else if(QComboBox *combo=qobject_cast<QComboBox*>(w))text=safeText(combo->currentText());
        if(!text.isEmpty())fprintf(out,"rc2_text=%s|%s|%s|%d,%d,%d,%d\n",w->metaObject()->className(),w->objectName().toUtf8().constData(),text.constData(),p.x(),p.y(),w->width(),w->height());
        if(QTabWidget *tabs=qobject_cast<QTabWidget*>(w)) {
            fprintf(out,"rc2_tabs=%s|%d|%d|%s\n",tabs->objectName().toUtf8().constData(),tabs->currentIndex(),tabs->count(),tabs->currentWidget()?tabs->currentWidget()->objectName().toUtf8().constData():"");
            QTabBar *bar=tabs->findChild<QTabBar*>("qt_tabwidget_tabbar");
            if(bar)fprintf(out,"rc2_tabbar=%s|%d,%d|%d\n",tabs->objectName().toUtf8().constData(),bar->width(),bar->height(),bar->isVisible());
        }
        if(QListView *view=qobject_cast<QListView*>(w)) {
            fprintf(out,"rc2_delegate=%s|%s\n",view->objectName().toUtf8().constData(),view->itemDelegate()?view->itemDelegate()->objectName().toUtf8().constData():"");
            if(view->model())for(int row=0;row<view->model()->rowCount();++row) {
                QModelIndex index=view->model()->index(row,0);QRect r=view->visualRect(index);QPoint top=view->viewport()->mapToGlobal(r.topLeft());
                fprintf(out,"rc2_list=%s|%d|%s|%d,%d,%d,%d\n",view->objectName().toUtf8().constData(),row,safeText(index.data().toString()).constData(),top.x(),top.y(),r.width(),r.height());
            }
        }
    }
    fputs("rc2_probe_complete=1\n",out);
    (void)action;
}
