// Scoped native Settings skin and the owner's requested Advanced-page access.
// All factory controls and their native signal handlers remain vendor-owned.
#include "settings_style.h"
#include "preferences.h"
#include <QtGui/qapplication.h>
#include <QtGui/qitemdelegate.h>
#include <QtGui/qlabel.h>
#include <QtGui/qlistview.h>
#include <QtGui/qpainter.h>
#include <QtGui/qtabwidget.h>
#include <QtCore/qcoreevent.h>
#include <QtCore/qpointer.h>
#include <QtCore/qregexp.h>
#include <QtCore/qvariant.h>
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

// The build headers use musl's time64 redirects; the vendor uses glibc time32.
extern "C" void *vendor_dlsym(void *,const char *) __asm__("dlsym");
#define dlsym vendor_dlsym

namespace {
bool settingsRoot(QWidget *w) {
    if(!w)return false;
    const char *name=w->metaObject()->className();
    return !strcmp(name,"SettingWindow")||!strcmp(name,"FactoryWindow")
        ||!strcmp(name,"FactorySettingWindow")||!strcmp(name,"MCUSettingWindow")
        ||!strcmp(name,"FKLearnWindow")||!strcmp(name,"VKLearnWindow")
        ||!strcmp(name,"SetWallpaper")||!strcmp(name,"BootlogoWindow");
}
bool revivalChild(QWidget *w,QWidget *root) {
    for(QWidget *p=w;p&&p!=root;p=p->parentWidget())
        if(p->objectName().startsWith("Revival"))return true;
    return false;
}
QWidget *rootFor(QWidget *widget) {
    for(QWidget *p=widget;p;p=p->parentWidget())if(settingsRoot(p))return p;
    return 0;
}

typedef QString(*McuVersionGetter)();
McuVersionGetter nativeMcuVersionGetter() {
    // The native successful PIN path uses this read-only QString getter. Its
    // hidden return-pointer ABI and entry are verified against libMsnCommons.
    static void *handle=dlopen("/usr/lib/libMsnCommons.so",RTLD_NOW|RTLD_NOLOAD);
    static McuVersionGetter getter=handle?(McuVersionGetter)dlsym(handle,"_Z17GetMCUVersion_MSNv"):0;
    static const uint32_t instructions[]={0xe59f32a8,0xe92d47f0,0xe1a06000,0xe08f3003};
    if(!getter)return 0;
    Dl_info info;
    if(!dladdr((void*)getter,&info)||!info.dli_fname||!info.dli_sname
       ||strcmp(info.dli_sname,"_Z17GetMCUVersion_MSNv")||info.dli_saddr!=(void*)getter
       ||(uintptr_t)getter-(uintptr_t)info.dli_fbase!=0x74b28)return 0;
    const char *file=strrchr(info.dli_fname,'/');
    if(strcmp(file?file+1:info.dli_fname,"libMsnCommons.so")
       ||memcmp((const void*)getter,instructions,sizeof(instructions)))return 0;
    return getter;
}

// The vendor delegate paints an orange resource pixmap itself, independently
// of QSS. Keep its row-size calculation but paint our own selection/background.
// The original model, view, current index and clicked connection are untouched.
class SettingsNavigation:public QItemDelegate {
    QPointer<QAbstractItemDelegate> native;
    QPointer<QListView> view;
public:
    SettingsNavigation(QListView *v):QItemDelegate(v),native(v->itemDelegate()),view(v) {
        setObjectName("RevivalSettingsNavigation");
    }
    QSize sizeHint(const QStyleOptionViewItem &option,const QModelIndex &index) const {
        return native?native->sizeHint(option,index):QSize(198,56);
    }
    void paint(QPainter *p,const QStyleOptionViewItem &option,const QModelIndex &index) const {
        const bool selected=(view&&view->currentIndex()==index)||(option.state&QStyle::State_Selected);
        const QColor accent=Revival::accentColor();
        p->save();p->setClipRect(option.rect);p->setRenderHint(QPainter::Antialiasing);
        QLinearGradient glass(option.rect.topLeft(),option.rect.bottomLeft());
        glass.setColorAt(0,selected?QColor(44,61,65):QColor(29,36,40));
        glass.setColorAt(1,selected?QColor(24,39,43):QColor(19,25,29));
        p->fillRect(option.rect,glass);
        p->setPen(QColor(61,72,78));p->drawLine(option.rect.bottomLeft(),option.rect.bottomRight());
        if(selected){p->fillRect(QRect(option.rect.left(),option.rect.top()+7,4,qMax(0,option.rect.height()-14)),accent);}
        QFont font=option.font;font.setPixelSize(21);font.setBold(selected);p->setFont(font);
        p->setPen((option.state&QStyle::State_Enabled)?QColor(238,243,242):QColor(123,136,141));
        QString label=index.data(Qt::DisplayRole).toString();
        QRect text=option.rect.adjusted(13,3,-10,-3);
        label=p->fontMetrics().elidedText(label,Qt::ElideRight,text.width());
        p->drawText(text,Qt::AlignVCenter|Qt::AlignLeft,label);p->restore();
    }
};

QString styleSheet() {
    QString accent=Revival::accentColor().name();
    return QString::fromLatin1(
        "QWidget{color:#eef3f2;background:transparent;}"
        "SettingWindow,FactoryWindow,FactorySettingWindow,MCUSettingWindow,"
        "FKLearnWindow,VKLearnWindow,SetWallpaper,BootlogoWindow{"
        "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #252f35,stop:0.55 #141b20,stop:1 #0e1317);}"
        "QFrame{border:0;} QLabel{border:0;background:transparent;color:#eef3f2;}"
        "QAbstractScrollArea{border:1px solid #405058;background:#192127;selection-background-color:%1;selection-color:#0f171b;}"
        "QAbstractScrollArea QWidget{background:#192127;}"
        "QListView#listViewSetItems,QListView#setItemListView{border:0;border-right:1px solid #46575f;background:#192127;}"
        "QPushButton,QToolButton{border-image:none;border:1px solid #53636b;border-radius:7px;"
        "color:#eef3f2;padding:3px 7px;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #38464e,stop:0.5 #29363e,stop:1 #1e292f);}"
        "QPushButton:pressed,QToolButton:pressed,QPushButton:checked,QToolButton:checked{border-color:%1;background:#344e56;}"
        "QPushButton:focus,QToolButton:focus{border:2px solid %1;}"
        "QPushButton:disabled,QToolButton:disabled{color:#7c8990;border-color:#344149;background:#1a2329;}"
        "QCheckBox,QRadioButton{color:#eef3f2;background:transparent;spacing:10px;}"
        "QCheckBox::indicator{width:23px;height:23px;border:2px solid #82959d;border-radius:4px;background:#111b21;}"
        "QCheckBox::indicator:checked{background:%1;border:2px solid #d7eeec;}"
        "QCheckBox::indicator:disabled{border-color:#4b585f;background:#283239;}"
        "QRadioButton::indicator{width:23px;height:23px;border:2px solid #82959d;border-radius:12px;background:#111b21;}"
        "QRadioButton::indicator:checked{background:%1;border:2px solid #d7eeec;}"
        "QLineEdit,QTextEdit,QPlainTextEdit,QComboBox,QSpinBox,QDoubleSpinBox{border:1px solid #586b75;border-radius:5px;"
        "padding:3px;color:#eef3f2;background:#152128;selection-background-color:%1;selection-color:#10191e;}"
        "QSlider::groove:horizontal{height:6px;border:1px solid #51636d;background:#10181e;border-radius:3px;}"
        "QSlider::sub-page:horizontal{background:%1;border-radius:3px;}"
        "QSlider::handle:horizontal{width:24px;margin:-10px 0;border:2px solid #e0eeee;border-radius:13px;background:%1;}"
        "QSlider::groove:vertical{width:6px;border:1px solid #51636d;background:#10181e;}"
        "QSlider::handle:vertical{height:24px;margin:0 -10px;border:2px solid #e0eeee;border-radius:13px;background:%1;}"
        "QScrollBar:vertical{width:18px;background:#141e24;}"
        "QScrollBar::handle:vertical{min-height:28px;border:1px solid #748991;border-radius:7px;background:#465f69;}"
        "QScrollBar:horizontal{height:18px;background:#141e24;}"
        "QScrollBar::handle:horizontal{min-width:28px;border:1px solid #748991;border-radius:7px;background:#465f69;}"
        "QTabWidget::pane{border:0;background:transparent;} QTabBar::tab{color:#e8eeed;background:#29373f;"
        "border:1px solid #50626b;padding:6px;} QTabBar::tab:selected{border-color:%1;background:#35505a;}"
        "QHeaderView::section{color:#e8eeed;background:#293a43;border:1px solid #53656f;padding:4px;}"
        "QProgressBar{border:1px solid #53656f;color:#eef3f2;background:#10181e;} QProgressBar::chunk{background:%1;}"
    ).arg(accent);
}
QString nativeIconStyle(const QString &sheet,bool rawContent=false) {
    // Native QSS also carries actual control content: FM arrows, display/EQ
    // page selectors, sound-field graphics and wheel-learning icons. Keep
    // those exact resource rules; btm_n/btm_h are merely the old orange button
    // decoration and are replaced by the glass button skin above.
    if(rawContent&&!sheet.contains('{')&&sheet.contains("url(")&&!sheet.contains("btm_"))return sheet;
    QString icons;QRegExp rule("([^{}]+)\\{([^{}]*)\\}");
    QRegExp contentId("#(?:btn|chk|icon|img|image)[A-Za-z0-9_]+");
    QRegExp zeroHeight("\\bheight\\s*:\\s*0+(?:px)?\\s*(?:;|$)");
    QRegExp zeroWidth("\\bwidth\\s*:\\s*0+(?:px)?\\s*(?:;|$)");
    int offset=0;
    while((offset=rule.indexIn(sheet,offset))>=0) {
        QString selector=rule.cap(1),body=rule.cap(2);
        // Several native panels use tab pages as an internal stack: their own
        // QSS gives the tab buttons zero size and positions the pane absolutely.
        // Those are structural rules, not decoration. Removing them exposes
        // untranslated internal tabs and shifts the real controls down.
        // Preserve only rules the native panel already supplied; visible user
        // tabs elsewhere retain their own size and normal native behaviour.
        bool hiddenTabs=selector.contains("QTabBar::tab")
            &&zeroHeight.indexIn(body)>=0&&zeroWidth.indexIn(body)>=0;
        bool absolutePane=selector.contains("QTabWidget::pane")
            &&body.contains("position")&&body.contains("absolute");
        if(hiddenTabs||absolutePane||(body.contains("url(")&&!body.contains("btm_")
           &&(contentId.indexIn(selector)>=0||body.contains("unchecked.png")||body.contains("checked.png"))))
            icons+=selector+"{"+body+"}";
        offset+=rule.matchedLength();
    }
    return icons;
}
void prepareChild(QWidget *w,QWidget *root) {
    if(w==root||revivalChild(w,root))return;
    w->setProperty("RevivalNativeStyleCleared",true);
    // Local vendor styles override an inherited sheet. Retain image-only
    // navigation/control content, and repeat if onLoadUiSkin resets the sheet.
    QString local=w->styleSheet(),previous=w->property("RevivalNativeIconStyle").toString();
    if(local!=previous) {
        // A raw image property applies only to this widget. Keep it regardless
        // of naming convention (the native FM map is called imageArea).
        QString icons=nativeIconStyle(local,true);w->setProperty("RevivalNativeIconStyle",icons);
        w->setStyleSheet(icons);
    }
    QListView *view=qobject_cast<QListView*>(w);
    if(view&&view->itemDelegate()
       &&!strcmp(view->itemDelegate()->metaObject()->className(),"SetItemListDelegate")
       &&view->itemDelegate()->objectName()!="RevivalSettingsNavigation") {
        view->setItemDelegate(new SettingsNavigation(view));
    }
}
}

namespace Revival {
void applySettingsStyle(QWidget *window) {
    if(!settingsRoot(window))return;
    // Cache per window and preference revision; the normal 500-ms discovery
    // pass must not repeatedly repolish every native Settings control.
    const unsigned revision=preferencesRevision();
    QVariant previous=window->property("RevivalSettingsTheme");
    if(previous.isValid()&&previous.toUInt()==revision
       &&window->styleSheet()==window->property("RevivalSettingsStyleSheet").toString())return;
    window->setProperty("RevivalSettingsTheme",QVariant(revision));
    QString existing=window->styleSheet();
    if(existing!=window->property("RevivalSettingsStyleSheet").toString())
        window->setProperty("RevivalSettingsNativeIcons",nativeIconStyle(existing));
    QList<QWidget*> children=window->findChildren<QWidget*>();
    for(int i=0;i<children.size();++i)prepareChild(children[i],window);
    QString sheet=styleSheet()+window->property("RevivalSettingsNativeIcons").toString();
    window->setProperty("RevivalSettingsStyleSheet",sheet);
    window->setStyleSheet(sheet);window->update();
}
void settingsStyleEvent(QObject *receiver,QEvent *event) {
    if(!receiver||!event||!receiver->isWidgetType())return;
    if(event->type()!=QEvent::Polish&&event->type()!=QEvent::Show)return;
    QWidget *widget=(QWidget*)receiver,*root=rootFor(widget);
    if(!root)return;
    prepareChild(widget,root);applySettingsStyle(root);
}
}

// The native Qt meta-call dispatch reaches this exact slot through the PLT.
// Its original four instructions only select tabPassword (index 0). The normal
// successful native PIN path selects tabAdminFunction (index 2), then fills and
// shows labMCUVersion using GetMCUVersion_MSN. Preserve both presentation steps
// without altering a password or any factory setting.
// If the exact ABI/widget contract differs, retain the native handler.
extern "C" void revival_advanced_page(void *)
    __asm__("_ZN13FactoryWindow26on_btnAdminSetting_clickedEv");
extern "C" void revival_advanced_page(void *self) {
    typedef void(*Slot)(void*);
    // Settings is a locally loaded plugin, so RTLD_NEXT from the preload's
    // global scope need not see it. Resolve the original through its already
    // loaded handle, as for the native attachItem/reboot APIs in ui.cpp.
    static void *handle=dlopen("/usr/lib/libSetting.so",RTLD_NOW|RTLD_NOLOAD);
    static Slot original=handle?(Slot)dlsym(handle,"_ZN13FactoryWindow26on_btnAdminSetting_clickedEv"):0;
    const bool nativeOriginal=original&&original!=&revival_advanced_page;
    static const uint32_t instructions[]={0xe5903050,0xe3a01000,0xe593000c,0xeafef5a6};
    QWidget *window=(QWidget*)self;
    if(nativeOriginal&&window&&!strcmp(window->metaObject()->className(),"FactoryWindow")
       &&!memcmp((const void*)original,instructions,sizeof(instructions))) {
        QTabWidget *tabs=window->findChild<QTabWidget*>("tabFactory");
        QLabel *version=window->findChild<QLabel*>("labMCUVersion");
        McuVersionGetter getVersion=nativeMcuVersionGetter();
        if(tabs&&tabs->count()==3&&tabs->widget(0)->objectName()=="tabPassword"
           &&tabs->widget(1)->objectName()=="tabFunction"&&tabs->widget(2)->objectName()=="tabAdminFunction"
           &&version&&getVersion) {
            Revival::applySettingsStyle(window);tabs->setCurrentIndex(2);
            version->setText(getVersion());version->show();
            fprintf(stderr,"REVIVAL: native Advanced settings opened without PIN\n");return;
        }
    }
    if(nativeOriginal)original(self);
}
