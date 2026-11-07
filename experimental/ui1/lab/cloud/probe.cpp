// Test-only widget/model fixtures in the isolated native ARM laboratory.
// Never enables P401_UI_LAB or changes the production hardware gate.
#include "name_store.h"
#include <QtGui/qapplication.h>
#include <QtGui/qlistview.h>
#include <QtGui/qstandarditemmodel.h>
#include <QtCore/qfile.h>
#include <QtCore/qvariant.h>
#include <QtCore/qpointer.h>
#include <QtCore/qcoreevent.h>
#include <stdio.h>
#include <dlfcn.h>
#include <string.h>
#include <stdlib.h>
extern "C" void *vendor_dlsym(void *,const char *) __asm__("dlsym");
#define dlsym vendor_dlsym
void settingsProbe(FILE *out);

static QPointer<QAbstractItemModel> originalModel;
static QPointer<QListView> originalView;
static int sourceShows=0,sourceHides=0,menuPaints=0;
static bool initialApplied=false,hiddenBeforePaint=false,hideScheduled=false;
static QByteArray menuCase() {
    char bytes[80];FILE *file=fopen("/lab/control/menu-case.txt","rb");
    if(!file)return QByteArray();size_t n=fread(bytes,1,sizeof(bytes),file);fclose(file);
    return QByteArray(bytes,int(n)).trimmed();
}

// Observe the real native handler's model lookup. The production code retains
// dlsym(handle, onItemClicked), so a substitute click handler would not prove it
// forwards the original row. This test-only model records that native lookup.
class TrackingModel:public QStandardItemModel {
public:TrackingModel(QObject *parent):QStandardItemModel(parent){}
    QVariant data(const QModelIndex &ix,int role=Qt::DisplayRole) const {
        QVariant value=QStandardItemModel::data(ix,role);
        Dl_info info;
        if(role==35&&dladdr(__builtin_return_address(0),&info)&&info.dli_sname
           &&strstr(info.dli_sname,"LauncherWindow13onItemClicked")) {
            FILE *out=fopen("/lab/control/native-click.txt","w");
            if(out){fprintf(out,"row=%d\nid=%d\n",ix.row(),value.toInt());fclose(out);}
        }
        return value;
    }
};
static QListView *findSource() {
    QWidgetList widgets=QApplication::allWidgets();
    for(int i=0;i<widgets.size();++i)if(widgets[i]->objectName()=="listviewMain")
        return qobject_cast<QListView*>(widgets[i]);
    return 0;
}
static bool changeModel(const QByteArray &action) {
    QListView *view=findSource();if(!view)return false;
    if(!originalModel&&view->model()){originalModel=view->model();originalView=view;}
    if(action=="model-restore") {if(originalModel){view->setModel(originalModel);return true;}return false;}
    if(action=="model-missing"){view->setModel(0);return true;}
    if(action=="model-empty"||action=="model-unknown-only"||action=="model-exit-only"||action=="model-main-only") {
        TrackingModel *model=new TrackingModel(view);
        if(action!="model-empty") {
            QStandardItem *item=new QStandardItem;
            item->setData(action=="model-unknown-only"?"Diagnostics":action=="model-main-only"?"CarPlay":" Exit ",Qt::DisplayRole);
            item->setData(action=="model-main-only"?4:31337,35);model->appendRow(item);
        }
        view->setModel(model);return true;
    }
    if(action=="unknown-exit"||action=="english-fixture") {
        QAbstractItemModel *old=view->model();if(!old)return false;
        TrackingModel *model=new TrackingModel(view);
        for(int row=0;row<old->rowCount();++row) {
            QModelIndex ix=old->index(row,0);QStandardItem *item=new QStandardItem;
            QMap<int,QVariant> roles=old->itemData(ix);
            for(QMap<int,QVariant>::const_iterator it=roles.constBegin();it!=roles.constEnd();++it)item->setData(it.value(),it.key());
            int id=old->data(ix,35).toInt();const char *label=0;
            switch(id){case 2:label="Music";break;case 4:label="CarPlay";break;case 5:id=13;label="Android Auto";break;case 11:label="Mirroring";break;case 3:label="Bluetooth";break;case 7:label="Video";break;case 9:label="Exit";break;case 8:label="Settings";break;}
            if(label)item->setData(label,Qt::DisplayRole);item->setData(id,35);
            if(action=="unknown-exit"&&id==9){item->setData(" Exit ",Qt::DisplayRole);item->setData(31337,35);}
            model->appendRow(item);
        }
        view->setModel(model);return true;
    }
    return false;
}
__attribute__((constructor)) static void probeLoaded(){fprintf(stderr,"CLOUD PROBE: loaded, menu case '%s'\n",menuCase().constData());}
static void testProbe() {
    QFile request("/lab/control/cloud-probe.request");
    if(!request.open(QIODevice::ReadOnly)) return;
    QByteArray action=request.readAll().trimmed();request.close();request.remove();
    bool changed=changeModel(action);
    if(action=="launcher-show"||action=="launcher-hide") {
        QWidgetList all=QApplication::allWidgets();
        for(int i=0;i<all.size();++i)if(!strcmp(all[i]->metaObject()->className(),"LauncherWindow")) {
            if(action=="launcher-show")all[i]->show();else all[i]->hide();
        }
    }
    QString saveError;bool saveAttempt=action.startsWith("save:");bool saved=saveAttempt&&Revival::saveName(QString::fromUtf8(action.mid(5)),saveError);
    QWidgetList widgets=QApplication::allWidgets();
    FILE *out=fopen("/lab/control/cloud-probe-results.txt","w");if(!out)return;
    fprintf(out,"laboratory=%d\nnames_available=%d\nsaved_name=%s\n",Revival::laboratory(),Revival::namesAvailable(),Revival::savedName().toUtf8().constData());
    fprintf(out,"menu_case=%s\n",menuCase().constData());
    fprintf(out,"model_changed=%d\nready_marker=%d\nsource_shows=%d\nsource_hides=%d\nmenu_paints=%d\nhidden_before_paint=%d\n",changed,QFile::exists("/tmp/p401-ui-ready"),sourceShows,sourceHides,menuPaints,hiddenBeforePaint);
    if(saveAttempt)fprintf(out,"save_result=%d\nsave_error=%s\n",saved,saveError.toUtf8().constData());
    QString visibleApps;
    void *common=dlopen("/usr/lib/libMsnCommons.so",RTLD_NOW|RTLD_NOLOAD);
    typedef unsigned(*AppId)(void*);AppId appId=common?(AppId)dlsym(common,"_ZN13MsnMainWindow8getAppIdEv"):0;
    for(int i=0;i<widgets.size();++i) {
        QWidget *w=widgets[i];QPoint p=w->mapToGlobal(QPoint(0,0));
        if(appId&&w->isVisible()&&w->inherits("MsnMainWindow")){if(!visibleApps.isEmpty())visibleApps+=",";visibleApps+=QString::number(appId(w));}
        fprintf(out,"widget=%s,%s,%d,%d,%d,%d,%d\n",w->metaObject()->className(),w->objectName().toUtf8().constData(),w->isVisible(),p.x(),p.y(),w->width(),w->height());
        if(w->objectName()=="listviewMain") {
            QListView *view=qobject_cast<QListView*>(w);if(!view)continue;
            fprintf(out,"source_hidden=%d\n",view->isHidden());
            if(!view->model())continue;QAbstractItemModel *model=view->model();
            fprintf(out,"source_rows=%d\n",model->rowCount());
            for(int row=0;row<model->rowCount();++row){QModelIndex ix=model->index(row,0);fprintf(out,"app=%d,%s\n",model->data(ix,35).toInt(),model->data(ix).toString().toUtf8().constData());}
        }
    }
    fprintf(out,"visible_apps=%s\n",visibleApps.toUtf8().constData());
    if(common)dlclose(common);settingsProbe(out);fclose(out);
}
class HideLauncherTimer:public QObject {
    QPointer<QWidget> target;
public:HideLauncherTimer(QWidget *w):QObject(qApp),target(w){startTimer(0);}
protected:void timerEvent(QTimerEvent *e) {
    killTimer(e->timerId());hiddenBeforePaint=true;
    fprintf(stderr,"CLOUD PROBE: queued launcher hide before first overlay paint\n");
    if(target)target->hide();deleteLater();
}
};
class ProbeFilter:public QObject {
public:ProbeFilter():QObject(qApp){}
protected:bool eventFilter(QObject *receiver,QEvent *event) {
    if(receiver->isWidgetType()) {
        QWidget *w=(QWidget*)receiver;
        if(w->objectName()=="listviewMain") {
            if(event->type()==QEvent::Show)++sourceShows;
            if(event->type()==QEvent::Hide)++sourceHides;
        }
        // The native list is constructed after Launcher Polish/Show. Inject
        // only once it exists, before a custom-menu paint could mark it ready.
        if(!initialApplied&&((w->objectName()=="RevivalNativeMenu"&&event->type()==QEvent::Paint)
           ||(w->objectName()=="listviewMain"&&(event->type()==QEvent::Show||event->type()==QEvent::Polish)))) {
            QByteArray mode=menuCase();
            if(mode=="initial-empty"||mode=="initial-missing"||mode=="initial-unknown-only") {
                QByteArray action=mode=="initial-empty"?"model-empty":mode=="initial-missing"?"model-missing":"model-unknown-only";
                if(changeModel(action)){initialApplied=true;fprintf(stderr,"CLOUD PROBE: initial model fixture %s\n",mode.constData());}
            }
        }
        if(w->objectName()=="RevivalNativeMenu"&&event->type()==QEvent::Paint) {
            if(menuCase()=="initial-hidden"&&!hiddenBeforePaint) {
                if(!hideScheduled){hideScheduled=true;new HideLauncherTimer(w->parentWidget());}
                return true;
            }
            ++menuPaints;
        }
    }
    return false;
}
};
class ProbeTimer:public QObject {
public:ProbeTimer():QObject(qApp){startTimer(100);fprintf(stderr,"CLOUD PROBE: timer scheduled\n");}
protected:void timerEvent(QTimerEvent *){testProbe();}
};
extern "C" bool probe_notify(void*,QObject*,QEvent*) __asm__("_ZN12QApplication6notifyEP7QObjectP6QEvent");
extern "C" bool probe_notify(void *self,QObject *receiver,QEvent *event) {
    typedef bool(*Notify)(void*,QObject*,QEvent*);
    static Notify real=(Notify)dlsym(RTLD_NEXT,"_ZN12QApplication6notifyEP7QObjectP6QEvent");
    static bool seen=false;if(!seen){seen=true;fprintf(stderr,"CLOUD PROBE: notify active, qApp=%p\n",qApp);}
    static bool filterInstalled=false;
    if(!filterInstalled&&qApp){filterInstalled=true;qApp->installEventFilter(new ProbeFilter);}
    static bool scheduled=false;
    if(!scheduled&&qApp&&event->type()==QEvent::Show){scheduled=true;new ProbeTimer;}
    return real?real(self,receiver,event):false;
}
