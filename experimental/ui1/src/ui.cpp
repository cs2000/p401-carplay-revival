// Native Qt 4.7.4 settings extension and explicitly isolated menu prototypes.
#include "name_store.h"
#include <QtGui/qapplication.h>
#include <QtGui/qwidget.h>
#include <QtGui/qpainter.h>
#include <QtGui/qpainterpath.h>
#include <QtGui/qpixmap.h>
#include <QtGui/qbrush.h>
#include <QtGui/qevent.h>
#include <QtGui/qboxlayout.h>
#include <QtGui/qlistview.h>
#include <QtGui/qdesktopwidget.h>
#include <QtCore/qfile.h>
#include <QtCore/qvector.h>
#include <QtCore/qvariant.h>
#include <QtCore/qpointer.h>
#include <QtCore/qdatetime.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
// Build headers use musl time64; the target is the vendor's glibc time32 ABI.
extern "C" void *vendor_dlsym(void *,const char *) __asm__("dlsym");
#define dlsym vendor_dlsym
#include "brand_paths.h"
#include "glass_artwork.h"

static QString tr(const char *s) { return QString::fromUtf8(s); }
static void text(QPainter &p,QRect r,const QString &s,int size,QColor c,int align=Qt::AlignCenter,bool bold=false) {
    QFont f("WenQuanYi Micro Hei");f.setPixelSize(size);f.setBold(bold);p.setFont(f);p.setPen(c);p.drawText(r,align,s);
}
static void icon(QPainter &p,int kind,int x,int y,int size,QColor color) {
    p.save();p.translate(x,y);p.scale(qreal(size)/64,qreal(size)/64);
    QPen pen(color);pen.setWidthF(2.4f);pen.setCapStyle(Qt::RoundCap);pen.setJoinStyle(Qt::RoundJoin);
    p.setPen(pen);p.setBrush(Qt::NoBrush);
    if(kind==0) { // phone and play mark
        p.drawRoundedRect(QRectF(10,5,33,53),4,4);p.drawLine(22,11,31,11);p.drawLine(22,51,30,51);
        p.setBrush(color);p.setPen(Qt::NoPen);QPainterPath a;a.moveTo(31,22);a.lineTo(51,33);a.lineTo(31,44);a.closeSubpath();p.drawPath(a);
    } else if(kind==1) {
        QPainterPath a;a.moveTo(11,49);a.lineTo(32,8);a.lineTo(53,49);a.lineTo(32,39);a.closeSubpath();p.drawPath(a);p.drawLine(32,39,32,54);
    } else if(kind==2) {
        QPainterPath a;a.moveTo(20,17);a.lineTo(46,43);a.lineTo(32,56);a.lineTo(32,7);a.lineTo(46,21);a.lineTo(20,47);p.drawPath(a);
    } else if(kind==3) {
        p.drawLine(26,45,26,14);p.drawLine(26,14,50,8);p.drawLine(50,8,50,39);p.drawLine(26,23,50,17);
        p.drawEllipse(QRectF(12,42,14,10));p.drawEllipse(QRectF(36,36,14,10));
    } else if(kind==4) {
        p.drawRoundedRect(QRectF(7,13,50,38),3,3);QPainterPath a;a.moveTo(27,22);a.lineTo(42,32);a.lineTo(27,42);a.closeSubpath();p.drawPath(a);
    } else if(kind==5) {
        p.drawRoundedRect(QRectF(6,10,42,31),2,2);p.drawRoundedRect(QRectF(37,26,20,31),2,2);p.drawLine(18,48,31,48);p.drawLine(25,42,25,48);p.drawLine(44,51,50,51);
    } else if(kind==6) {
        QPainterPath door;door.moveTo(29,9);door.lineTo(9,9);door.lineTo(9,55);door.lineTo(29,55);p.drawPath(door);
        p.drawLine(25,32,56,32);QPainterPath arrow;arrow.moveTo(44,20);arrow.lineTo(56,32);arrow.lineTo(44,44);p.drawPath(arrow);
    } else {
        QPainterPath a;
        for(int j=0;j<32;++j) { qreal r=(j%4==1||j%4==2)?25:20; qreal ang=qreal(j)*6.2831853f/32;
            QPointF v(32+r*cosf(ang),32+r*sinf(ang));if(j)a.lineTo(v);else a.moveTo(v); }
        a.closeSubpath();p.drawPath(a);p.drawEllipse(QRectF(23,23,18,18));
    }
    p.restore();
}
struct Hit { QRect rect; QString action; Hit(){} Hit(QRect r,QString a):rect(r),action(a){} };
static QColor bg(14,17,18),surface(31,36,38),ink(240,241,238),muted(165,175,176),teal(95,205,199),red(208,64,51);
static void fitArtwork(QPainter &p,const QPainterPath &path,QRectF area,QColor color) {
    QRectF b=path.boundingRect();qreal s=qMin(area.width()/b.width(),area.height()/b.height());
    p.save();p.translate(area.center());p.scale(s,s);p.translate(-b.center());p.fillPath(path,color);p.restore();
}
static void drawBrand(QPainter &p,QRect area) {
    static const QPainterPath logo=jaguar_stacked();
    p.save();p.setRenderHint(QPainter::Antialiasing);p.translate(area.x(),area.y());p.scale(qreal(area.width())/340,qreal(area.height())/60);
    fitArtwork(p,logo,QRectF(107.5f,3,125,54),ink);p.restore();
}
// Scope the extension to this process: its spawned CarPlay/radio services must
// not inherit LD_PRELOAD or load our Qt UI library.
__attribute__((constructor)) static void isolatePreload(){unsetenv("LD_PRELOAD");}
static QPointer<QWidget> settingsInstance;
static void *settingSymbol(const char *name) {
    static void *handle=dlopen("/usr/lib/libSetting.so",RTLD_NOW|RTLD_NOLOAD);
    return handle?dlsym(handle,name):0;
}
static bool restartAvailable() {
    if(Revival::laboratory()) return true;
    typedef int(*Lock)(); Lock f=(Lock)dlsym(RTLD_DEFAULT,"_Z24GetRebootSystemLockCountv");
    return settingsInstance && f && f()==0 && settingSymbol("_ZN13SettingWindow8onRebootEv");
}

class NameEditor:public QWidget {
    QVector<Hit> hits;QString draft,error;bool caps,confirm,restarting;int pressed;
    void button(QPainter &p,QRect r,QString label,QString action,bool primary=false) {
        bool down=pressed==hits.size();p.fillRect(r,down?QColor(63,85,85):(primary?QColor(45,92,90):surface));
        p.setPen(primary?teal:QColor(72,79,80));p.drawRect(r.adjusted(0,0,-1,-1));text(p,r,label,22,ink);hits.append(Hit(r,action));
    }
public:
    NameEditor():QWidget(0,Qt::FramelessWindowHint|Qt::WindowStaysOnTopHint),caps(true),confirm(false),restarting(false),pressed(-1) {
        draft=Revival::savedName();setAttribute(Qt::WA_DeleteOnClose);setGeometry(QApplication::desktop()->screenGeometry());setObjectName("RevivalNameEditor");
    }
protected:
    void paintEvent(QPaintEvent *) {
        QPainter p(this);p.fillRect(rect(),bg);p.scale(qreal(width())/800,qreal(height())/480);p.setRenderHint(QPainter::Antialiasing);hits.clear();
        text(p,QRect(24,10,752,43),tr("CarPlay name"),26,ink,Qt::AlignLeft|Qt::AlignVCenter);
        p.setPen(teal);p.drawLine(24,59,776,59);
        if(!Revival::namesAvailable()) {
            text(p,QRect(40,155,720,120),Revival::namesUnavailableReason(),23,muted,Qt::AlignCenter|Qt::TextWordWrap);
            button(p,QRect(24,414,752,52),tr("Close"),"cancel");return;
        }
        if(restarting) {text(p,QRect(40,185,720,48),tr("Restarting…"),30,ink);return;}
        if(confirm) {
            text(p,QRect(32,90,736,55),draft,30,ink);
            text(p,QRect(35,165,730,75),tr("Use this name for Wi-Fi and Bluetooth?"),23,ink);
            text(p,QRect(35,235,730,65),tr("The unit will restart. You may need to pair your phone again."),19,muted,Qt::AlignCenter|Qt::TextWordWrap);
            button(p,QRect(24,392,354,64),tr("Go back"),"back");button(p,QRect(394,392,382,64),tr("Save & restart"),"commit",true);return;
        }
        p.fillRect(QRect(24,73,752,57),QColor(8,11,12));p.setPen(teal);p.drawRect(24,73,751,56);
        text(p,QRect(39,79,710,45),draft.isEmpty()?tr("Enter a name"):draft,26,draft.isEmpty()?muted:ink,Qt::AlignLeft|Qt::AlignVCenter);
        const char *rows[]={"1234567890","QWERTYUIOP","ASDFGHJKL","ZXCVBNM"};
        for(int row=0;row<4;++row) {
            QString letters=tr(rows[row]);int x=(800-letters.size()*75)/2;
            for(int j=0;j<letters.size();++j) {QString s=letters.mid(j,1);if(!caps)s=s.toLower();button(p,QRect(x+j*75,143+row*51,69,46),s,"key:"+s);}
        }
        button(p,QRect(24,350,120,46),caps?tr("abc"):tr("ABC"),"caps");
        button(p,QRect(151,350,81,46),"-","key:-");button(p,QRect(239,350,81,46),"_","key:_");
        button(p,QRect(327,350,285,46),tr("Space"),"key: ");button(p,QRect(619,350,157,46),tr("Delete"),"delete");
        button(p,QRect(24,414,167,52),tr("Cancel"),"cancel");
        text(p,QRect(205,410,327,55),error.isEmpty()?tr("1–24 letters, numbers, spaces, - or _"):error,16,error.isEmpty()?muted:red,Qt::AlignCenter|Qt::TextWordWrap);
        button(p,QRect(546,414,230,52),tr("Continue"),"confirm",true);
    }
    int hitAt(QPoint pos) {QPoint pt(pos.x()*800/qMax(width(),1),pos.y()*480/qMax(height(),1));for(int i=0;i<hits.size();++i)if(hits[i].rect.contains(pt))return i;return -1;}
    void mousePressEvent(QMouseEvent *e) {pressed=hitAt(e->pos());update();}
    void mouseReleaseEvent(QMouseEvent *e) {
        if(!Revival::namesAvailable()) {close();return;}
        int h=hitAt(e->pos());if(h<0||h!=pressed){pressed=-1;update();return;}QString a=hits[h].action;pressed=-1;
        if(a.startsWith("key:")) {if(draft.size()<24)draft+=a.mid(4);}
        else if(a=="caps") caps=!caps;
        else if(a=="delete") draft.chop(1);
        else if(a=="cancel") {close();return;}
        else if(a=="back") confirm=false;
        else if(a=="confirm") {draft=draft.trimmed();if(Revival::validName(draft)){error.clear();confirm=true;}else error=tr("Enter a name first.");}
        else if(a=="commit") {
            if(!restartAvailable()) {confirm=false;error=tr("Restart is busy. Please try again.");}
            else if(Revival::saveName(draft,error)){restarting=true;startTimer(700);}
            else confirm=false;
        }
        update();
    }
    void timerEvent(QTimerEvent *e) {
        killTimer(e->timerId());
        if(Revival::laboratory()) {close();return;}
        typedef void(*Fn)(void*);Fn f=(Fn)settingSymbol("_ZN13SettingWindow8onRebootEv");
        if(f&&settingsInstance)f(settingsInstance.data());
        restarting=false;confirm=false;error=tr("Name saved. Restart the unit to apply it.");update();
    }
};

class NamePanel:public QWidget {
public:NamePanel(){setObjectName("RevivalNamePanel");}
protected:
    void paintEvent(QPaintEvent *) {
        QPainter p(this);p.fillRect(rect(),bg);
        text(p,QRect(20,25,width()-40,50),tr("Wi-Fi and Bluetooth name"),24,ink);
        bool available=Revival::namesAvailable();
        QString name=Revival::savedName();text(p,QRect(20,100,width()-40,55),available?(name.isEmpty()?tr("Use the device’s default name"):name):tr("Custom naming unavailable"),24,available?teal:muted);
        p.fillRect(QRect(30,185,width()-60,65),surface);text(p,QRect(30,185,width()-60,65),available?tr("Change name"):tr("Unavailable"),23,available?ink:muted);
        text(p,QRect(20,265,width()-40,110),available?tr("Saving a new name restarts the unit. Your other settings stay as they are."):Revival::namesUnavailableReason(),18,muted,Qt::AlignCenter|Qt::TextWordWrap);
    }
    void mouseReleaseEvent(QMouseEvent *e) {if(Revival::namesAvailable()&&QRect(30,185,width()-60,65).contains(e->pos())){NameEditor *v=new NameEditor;v->show();v->raise();}}
};

static void attachSettings(void *self) {
    if(settingsInstance==self)return;
    typedef void(*Attach)(void*,QString,QString,QLayout*);
    Attach attach=(Attach)settingSymbol("_ZN13SettingWindow10attachItemE7QStringS0_P7QLayout");
    if(attach){settingsInstance=(QWidget*)self;QVBoxLayout *layout=new QVBoxLayout;layout->setContentsMargins(0,0,0,0);layout->addWidget(new NamePanel);attach(self,"RevivalCarPlayName","CarPlay name",layout);fprintf(stderr,"REVIVAL: CarPlay name Settings page attached\n");}
}

class HomeBrand:public QWidget {
    QString clockText;
public:HomeBrand(QWidget *parent):QWidget(parent),clockText(QTime::currentTime().toString("HH:mm")) {
        setAttribute(Qt::WA_TransparentForMouseEvents);setObjectName("RevivalHomeBrand");startTimer(1000);
    }
protected:
    void timerEvent(QTimerEvent *) {
        QString current=QTime::currentTime().toString("HH:mm");
        if(current!=clockText){clockText=current;update();}
    }
    void paintEvent(QPaintEvent *) {
        QPainter p(this);p.fillRect(rect(),Qt::black);p.scale(qreal(width())/486,qreal(height())/60);
        // Cover the home title only while the themed launcher is visible. The
        // clock occupies its old slot; the logo retains screen centre x=400.
        text(p,QRect(6,0,130,60),clockText,25,ink,Qt::AlignLeft|Qt::AlignVCenter);
        drawBrand(p,QRect(146,0,340,60));
    }
};
struct AppEntry {int row,id,kind;QString label;AppEntry():row(-1),id(0),kind(8){} };
static int appKind(int id,QString label) {
    // Native IDs preserve the layout when the user selects another language.
    switch(id){case 4:return 0;case 13:return 1;case 3:return 2;case 2:return 3;case 7:return 4;case 11:return 5;case 9:return 6;case 8:return 7;}
    // Field profiles may supply an explicit Exit row with a different native
    // ID. Keep its original row action; only classify the exact displayed name.
    QString n=label.simplified().toLower();
    if(n.contains("carplay"))return 0;if(n.contains("android"))return 1;
    if(n.contains("bluetooth"))return 2;if(n.contains("music"))return 3;
    if(n.contains("video"))return 4;if(n.contains("mirror"))return 5;
    if(n=="exit"||n=="av in"||n=="original car")return 6;if(n.contains("setting"))return 7;
    return 8;
}
class NativeMenu:public QWidget {
    QPointer<QListView> source;QPointer<HomeBrand> brand;QVector<AppEntry> apps;QVector<Hit> hits;int pressed;QWidget *launcher;QString modelState;
    bool ready,abandoned;int startupTicks;
    bool modelAvailable() const {
        if(!source||!source->model())return false;
        QAbstractItemModel *model=source->model();bool main=false,settings=false;
        for(int row=0;row<model->rowCount();++row) {
            QModelIndex ix=model->index(row,0);
            int kind=appKind(model->data(ix,35).toInt(),model->data(ix,Qt::DisplayRole).toString());
            if(kind>=0&&kind<=5)main=true;if(kind==7)settings=true;
        }
        return main&&settings;
    }
    bool bindSource() {
        if(!source)source=launcher->findChild<QListView*>("listviewMain");
        if(!source)return false;
        bool available=modelAvailable();
        // Leave the stock view alone after failing open. Repeated hide/show
        // cycles here would repaint it twice a second after a model loss.
        if(available||!ready){if(!source->isHidden())source->hide();}
        else if(source->isHidden())source->show();
        return available;
    }
    void attachBrand() {
        if(!brand) {
            QWidgetList widgets=QApplication::allWidgets();
            for(int i=0;i<widgets.size();++i)if(!strcmp(widgets[i]->metaObject()->className(),"StatusBar")) {
                brand=new HomeBrand(widgets[i]);break;
            }
        }
        if(brand) {
            QWidget *bar=brand->parentWidget();
            QRect area(bar->width()*84/800,0,bar->width()*486/800,qMax(0,bar->height()-1));
            if(brand->geometry()!=area)brand->setGeometry(area);
            if(isVisible()) {
                if(brand->isHidden())brand->show();
                if(bar->children().last()!=brand.data())brand->raise();
            }
        }
    }
    void markReady() {
        if(ready)return;
        QFile file("/tmp/p401-ui-ready");
        if(file.open(QIODevice::WriteOnly)&&file.write("ready\n")==6&&file.flush()) {
            ready=true;fprintf(stderr,"REVIVAL: native XFR menu attached; original application actions retained\n");
        }
    }
    static const QPixmap &tileArtwork() {
        // Decode once per GUI process. These are static tile pictures; there is
        // no animated wallpaper, blur pass, network fetch or background timer.
        static QPixmap atlas;
        static bool loaded=false;
        if(!loaded) {
            loaded=true;
            if(atlas.loadFromData(p401_glass_tile_atlas,p401_glass_tile_atlas_size,"PNG")) {
                // Bound the retained raster to 1.5 MiB at 32 bpp, even when the
                // source artwork was generated at a much larger resolution.
                if(atlas.width()>768||atlas.height()>512)atlas=atlas.scaled(768,512,Qt::KeepAspectRatio,Qt::SmoothTransformation);
                fprintf(stderr,"REVIVAL: static glass artwork loaded %dx%d\n",atlas.width(),atlas.height());
            } else fprintf(stderr,"REVIVAL: glass artwork unavailable; using graphite tiles\n");
        }
        return atlas;
    }
    void tile(QPainter &p,const AppEntry &app,QRect r,bool flat=false) {
        bool down=pressed==hits.size();
        QRectF card(r.adjusted(1,1,-1,-1));
        QPainterPath outline;outline.addRoundedRect(card,10,10);
        p.save();
        p.setClipPath(outline);
        QLinearGradient base(card.topLeft(),card.bottomLeft());
        base.setColorAt(0,QColor(58,63,66));base.setColorAt(1,QColor(20,25,28));
        p.fillPath(outline,base);
        if(!flat&&app.kind>=0&&app.kind<6) {
            const QPixmap &atlas=tileArtwork();
            if(!atlas.isNull()) {
                // Crop within each atlas cell, so a different screen aspect
                // never stretches the pictures or leaks a neighbouring tile.
                qreal w=qreal(atlas.width())/3,h=qreal(atlas.height())/2;
                QRectF photo((app.kind%3)*w,(app.kind/3)*h,w,h);
                qreal ratio=card.width()/card.height();
                if(photo.width()/photo.height()>ratio){qreal crop=photo.height()*ratio;photo.setX(photo.x()+(photo.width()-crop)/2);photo.setWidth(crop);}
                else {qreal crop=photo.width()/ratio;photo.setY(photo.y()+(photo.height()-crop)/2);photo.setHeight(crop);}
                p.setRenderHint(QPainter::SmoothPixmapTransform);p.drawPixmap(card,atlas,photo);
            }
            QLinearGradient shade(card.topLeft(),card.bottomLeft());
            shade.setColorAt(0,QColor(6,12,16,75));shade.setColorAt(.48f,QColor(5,10,14,95));shade.setColorAt(1,QColor(4,8,11,230));
            p.fillPath(outline,shade);
        }
        if(down)p.fillPath(outline,QColor(53,150,146,65));
        // A quiet upper reflection gives the glass depth without rendering a
        // real-time effect. Large labels retain contrast over every picture.
        QLinearGradient sheen(card.topLeft(),QPointF(card.left(),card.top()+card.height()*.48f));
        sheen.setColorAt(0,QColor(255,255,255,30));sheen.setColorAt(1,QColor(255,255,255,0));
        p.fillPath(outline,sheen);p.restore();
        p.save();p.setBrush(Qt::NoBrush);
        p.setPen(QPen(down?teal:(app.kind==0?QColor(87,176,173):QColor(114,125,130)),1));p.drawPath(outline);
        p.setPen(QColor(255,255,255,65));p.drawLine(QPointF(card.left()+11,card.top()+1),QPointF(card.right()-11,card.top()+1));
        if(flat) {
            icon(p,app.kind,r.x()+16,r.y()+16,40,QColor(0,0,0,160));
            icon(p,app.kind,r.x()+16,r.y()+15,40,ink);
            text(p,QRect(r.x()+74,r.y(),r.width()-84,r.height()),app.label,23,ink,Qt::AlignLeft|Qt::AlignVCenter);
        } else {
            int size=qMin(49,r.height()-62),box=size+16;
            QRectF badge(r.x()+(r.width()-box)/2,r.y()+10,box,box);
            QPainterPath glass;glass.addRoundedRect(badge,12,12);
            QLinearGradient tint(badge.topLeft(),badge.bottomLeft());
            tint.setColorAt(0,QColor(225,238,242,75));tint.setColorAt(.49f,QColor(115,139,147,40));tint.setColorAt(.51f,QColor(8,20,26,125));tint.setColorAt(1,QColor(15,29,35,155));
            p.fillPath(glass,tint);p.setPen(QColor(225,245,245,95));p.drawPath(glass);
            icon(p,app.kind,int(badge.x())+8,int(badge.y())+10,size,QColor(0,0,0,180));
            icon(p,app.kind,int(badge.x())+8,int(badge.y())+8,size,app.kind==0?QColor(143,237,229):ink);
            QRect label(r.x()+4,r.bottom()-38,r.width()-8,34);
            text(p,label.translated(0,1),app.label,21,QColor(0,0,0,230));text(p,label,app.label,21,ink);
        }
        p.restore();hits.append(Hit(r,QString::number(app.row)));
    }
public:
    NativeMenu(QWidget *parent):QWidget(parent),pressed(-1),launcher(parent),ready(false),abandoned(false),startupTicks(0) {
        setObjectName("RevivalNativeMenu");setAttribute(Qt::WA_OpaquePaintEvent);setGeometry(parent->rect());parent->installEventFilter(this);
        attachBrand();bindSource();startTimer(500);
    }
    void prepareForShow(bool forceStack=false) {
        if(abandoned)return;
        if(!bindSource()&&ready){if(!isHidden())hide();return;}
        if(geometry()!=launcher->rect())setGeometry(launcher->rect());
        if(isHidden())show();
        if(forceStack||launcher->children().last()!=this)raise();
    }
protected:
    void showEvent(QShowEvent *) {attachBrand();}
    void hideEvent(QHideEvent *) {if(brand)brand->hide();}
    bool eventFilter(QObject *o,QEvent *e) {
        if(o==launcher) {
            if(e->type()==QEvent::Resize&&geometry()!=launcher->rect())setGeometry(launcher->rect());
            if(!abandoned&&(e->type()==QEvent::ChildAdded||e->type()==QEvent::ChildPolished)
               &&launcher->children().last()!=this)raise();
        }
        return false;
    }
    void timerEvent(QTimerEvent *) {
        if(abandoned)return;
        attachBrand();
        if(!bindSource()) {
            if(ready||++startupTicks>=120) {
                // Fail open even when run without the shell watchdog. In the
                // packaged runner a missing ready marker also triggers stock
                // fallback after 60 seconds; do not mark an empty or unrelated
                // model ready.
                if(!isHidden())hide();if(source&&source->isHidden())source->show();
                if(!ready){abandoned=true;fprintf(stderr,"REVIVAL: launcher model unavailable; showing original interface\n");}
            }
            return;
        }
        if(launcher->isVisible())prepareForShow();
        else {
            // An automatic vendor application may hide Home before it ever
            // paints. A validated model and attached overlay are sufficient
            // here; do not restart an active app waiting for an invisible paint.
            markReady();
        }
        // Redraw only when the source app list changes. Repainting a static
        // screen twice a second wastes the old ARM CPU and causes visible tears
        // when the simulator captures a framebuffer partway through a paint.
        QString state;QAbstractItemModel *m=source->model();
        for(int i=0;i<m->rowCount();++i){QModelIndex ix=m->index(i,0);state+=QString::number(m->data(ix,35).toInt())+":"+m->data(ix).toString()+"\n";}
        if(state!=modelState||!ready){modelState=state;update();}
    }
    void paintEvent(QPaintEvent *) {
        QPainter p(this);p.scale(qreal(width())/800,qreal(height())/480);p.setRenderHint(QPainter::Antialiasing);p.fillRect(QRect(0,0,800,480),bg);
        hits.clear();apps.clear();AppEntry av,settings;
        if(!modelAvailable()) {
            drawBrand(p,QRect(230,160,340,60));text(p,QRect(24,250,752,44),tr("Starting…"),22,muted);return;
        }
        QAbstractItemModel *model=source->model();
        for(int row=0;row<model->rowCount();++row){AppEntry a;a.row=row;QModelIndex ix=model->index(row,0);a.label=model->data(ix,Qt::DisplayRole).toString();a.id=model->data(ix,35).toInt();a.kind=appKind(a.id,a.label);if(a.kind==6){a.label=tr("Exit");av=a;}else if(a.kind==7)settings=a;else apps.append(a);}
        // Retain every configured app. Known functions follow the selected layout.
        for(int i=0;i<apps.size();++i)for(int j=i+1;j<apps.size();++j)if(apps[j].kind<apps[i].kind){AppEntry a=apps[i];apps[i]=apps[j];apps[j]=a;}
        int rows=apps.size()>8?3:2;int cols=qMax(1,(apps.size()+rows-1)/rows);int cell=762/cols;int height=278/rows;
        p.setPen(teal);p.drawLine(24,64,776,64);
        for(int i=0;i<apps.size();++i)tile(p,apps[i],QRect(24+(i%cols)*cell,86+(i/cols)*height,cell-10,height-10));
        if(av.row>=0&&settings.row>=0){tile(p,av,QRect(24,373,366,71),true);tile(p,settings,QRect(406,373,370,71),true);}
        else if(settings.row>=0)tile(p,settings,QRect(24,373,752,71),true);
        else if(av.row>=0)tile(p,av,QRect(24,373,752,71),true);
        p.end();markReady();
    }
    int hitAt(QPoint pos){QPoint p(pos.x()*800/qMax(width(),1),pos.y()*480/qMax(height(),1));for(int i=0;i<hits.size();++i)if(hits[i].rect.contains(p))return i;return -1;}
    void mousePressEvent(QMouseEvent *e){pressed=hitAt(e->pos());update();}
    void mouseReleaseEvent(QMouseEvent *e){int h=hitAt(e->pos());if(h>=0&&h==pressed&&source&&source->model()){
        int row=hits[h].action.toInt();void *lib=dlopen("/usr/lib/libLauncher-Box.so",RTLD_NOW|RTLD_NOLOAD);
        typedef void(*Click)(void*,QModelIndex);Click click=lib?(Click)dlsym(lib,"_ZN14LauncherWindow13onItemClickedE11QModelIndex"):0;
        if(click)click(launcher,source->model()->index(row,0));if(lib)dlclose(lib);
    }pressed=-1;update();}
};
static QPointer<NativeMenu> nativeMenu;
static void attachMenu(QWidget *window,bool forceStack=false) {
    if(!getenv("P401_UI_LAYOUT"))return;
    if(!nativeMenu)nativeMenu=new NativeMenu(window);
    if(nativeMenu->parentWidget()==window)nativeMenu->prepareForShow(forceStack);
}

static const char *appNames[]={"CarPlay","Android Auto","Bluetooth","USB music","USB video","Phone mirroring","Exit","Settings"};
class DesignWindow:public QWidget {
    QVector<Hit> hits;int design,pressed,page;QString current;
    void tile(QPainter &p,int app,QRect r,bool list=false) {
        bool down=pressed==hits.size();QColor accent=teal;
        if(design==0 || design==1) {
            p.fillRect(r,down?QColor(47,61,62):surface);p.setPen(design==0?QColor(70,78,79):QColor(48,51,52));p.drawRect(r.adjusted(0,0,-1,-1));
            if(design==1){p.fillRect(QRect(r.x(),r.y(),3,r.height()),app==0?teal:QColor(68,69,68));}
        } else {p.fillRect(r,down?QColor(39,53,53):bg);p.setPen(QColor(58,64,65));p.drawLine(r.left(),r.bottom(),r.right(),r.bottom());}
        if(list) {icon(p,app,r.x()+14,r.y()+(r.height()-42)/2,42,app==0?accent:ink);text(p,QRect(r.x()+73,r.y(),r.width()-83,r.height()),tr(appNames[app]),23,ink,Qt::AlignLeft|Qt::AlignVCenter);}
        else {icon(p,app,r.x()+(r.width()-58)/2,r.y()+18,58,app==0?accent:ink);text(p,QRect(r.x()+3,r.y()+82,r.width()-6,40),tr(appNames[app]),20,ink);}
        hits.append(Hit(r,QString::number(app)));
    }
public:
    DesignWindow():QWidget(0,Qt::FramelessWindowHint|Qt::WindowStaysOnTopHint),design(0),pressed(-1),page(0) {setGeometry(0,0,800,480);setObjectName("RevivalMenuPreview");startTimer(300);}
protected:
    void timerEvent(QTimerEvent *) {
        QFile f("/lab/control/design.txt");if(f.open(QIODevice::ReadOnly)){int n=QString::fromLatin1(f.readAll()).trimmed().toInt();if(n>=0&&n<=2&&design!=n){design=n;page=0;update();}}
        QString n=Revival::savedName();if(n!=current){current=n;update();}
    }
    void paintEvent(QPaintEvent *) {
        QPainter p(this);p.setRenderHint(QPainter::Antialiasing);p.fillRect(rect(),bg);hits.clear();
        QColor accent=teal;
        text(p,QRect(24,12,200,44),page?tr("Settings"):tr("Home"),25,ink,Qt::AlignLeft|Qt::AlignVCenter);
        drawBrand(p,QRect(230,0,340,60));
        text(p,QRect(666,12,110,44),"09:41",23,muted,Qt::AlignRight|Qt::AlignVCenter);
        p.setPen(accent);p.drawLine(24,64,776,64);
        if(page==1) {
            p.fillRect(QRect(24,94,752,105),surface);text(p,QRect(45,99,710,42),tr("CarPlay name"),25,ink,Qt::AlignLeft|Qt::AlignVCenter);
            text(p,QRect(45,145,710,38),current.isEmpty()?tr("Device default"):current,22,accent,Qt::AlignLeft|Qt::AlignVCenter);
            hits.append(Hit(QRect(24,94,752,105),"name"));
            text(p,QRect(35,223,730,75),tr("One name for Wi-Fi and Bluetooth.\nA restart applies your change."),22,muted);
            p.fillRect(QRect(24,398,240,58),surface);text(p,QRect(24,398,240,58),tr("Back to home"),22,ink);hits.append(Hit(QRect(24,398,240,58),"home"));return;
        }
        if(page>=2) {
            int app=page-2;icon(p,app,352,139,96,accent);text(p,QRect(25,250,750,45),tr(appNames[app]),28,ink);
            text(p,QRect(40,306,720,43),tr("App screen placeholder"),20,muted);
            p.fillRect(QRect(260,391,280,64),surface);text(p,QRect(260,391,280,64),tr("Back to home"),23,ink);hits.append(Hit(QRect(260,391,280,64),"home"));return;
        }
        if(design==0) {
            for(int i=0;i<8;++i)tile(p,i,QRect(24+(i%4)*190,90+(i/4)*170,182,152));
        } else if(design==1) {
            for(int i=0;i<6;++i)tile(p,i,QRect(24+(i%3)*254,86+(i/3)*139,244,129));
            tile(p,6,QRect(24,373,366,71),true);tile(p,7,QRect(406,373,370,71),true);
        } else {
            for(int i=0;i<8;++i)tile(p,i,QRect(24+(i%2)*386,86+(i/2)*84,365,76),true);
        }
        if(design==0)text(p,QRect(24,434,752,32),current.isEmpty()?tr("Wireless connectivity"):current,16,muted);
    }
    int hitAt(QPoint p){for(int i=0;i<hits.size();++i)if(hits[i].rect.contains(p))return i;return -1;}
    void mousePressEvent(QMouseEvent *e){pressed=hitAt(e->pos());update();}
    void mouseReleaseEvent(QMouseEvent *e){int h=hitAt(e->pos());if(h>=0&&h==pressed){QString a=hits[h].action;if(a=="name"){NameEditor *v=new NameEditor;v->show();v->raise();}else if(a=="home")page=0;else {int app=a.toInt();page=app==7?1:app+2;}}pressed=-1;update();}
};

void runLabProbe();
class PreviewTimer:public QObject {
    bool first;
public:PreviewTimer():QObject(qApp),first(true){startTimer(500);}
protected:void timerEvent(QTimerEvent *){
    runLabProbe();
    QWidgetList current=QApplication::allWidgets();
    for(int i=0;i<current.size();++i)if(current[i]->isVisible()) {
        const char *name=current[i]->metaObject()->className();
        if(!strcmp(name,"LauncherWindow"))attachMenu(current[i]);
        if(!strcmp(name,"SettingWindow"))attachSettings(current[i]);
    }
    if(!first)return;first=false;
    if(!Revival::laboratory())return;
    FILE *out=fopen("/lab/control/widget-tree.txt","w");
    if(out){QWidgetList ws=QApplication::allWidgets();for(int i=0;i<ws.size();++i){QWidget *w=ws[i];QPoint pos=w->mapToGlobal(QPoint(0,0));fprintf(out,"%s %s visible=%d rect=%d,%d,%d,%d\n",w->metaObject()->className(),w->objectName().toUtf8().constData(),w->isVisible(),pos.x(),pos.y(),w->width(),w->height());QListView *v=qobject_cast<QListView*>(w);if(v&&v->model()){for(int j=0;j<v->model()->rowCount();++j)fprintf(out," ROW %d %s\n",j,v->model()->data(v->model()->index(j,0),Qt::DisplayRole).toString().toUtf8().constData());}}fclose(out);}
    if(getenv("P401_UI_DEMO")){DesignWindow *w=new DesignWindow;w->show();w->raise();fprintf(stderr,"REVIVAL: native ARM menu preview opened\n");}
}
};

extern "C" bool notify_hook(void *,QObject *,QEvent *) __asm__("_ZN12QApplication6notifyEP7QObjectP6QEvent");
extern "C" bool notify_hook(void *self,QObject *receiver,QEvent *event) {
    typedef bool(*Fn)(void*,QObject*,QEvent*);static Fn real=(Fn)dlsym(RTLD_NEXT,"_ZN12QApplication6notifyEP7QObjectP6QEvent");
    static bool scheduled=false;
    if(!scheduled && qApp && event->type()==QEvent::Show){scheduled=true;new PreviewTimer;}
    // Cover the launcher before its first exposure, including the period when
    // the vendor app list is still being populated. Dispatch its normal events
    // so service startup and the stock fallback remain independent of the UI.
    if(receiver->isWidgetType()&&(event->type()==QEvent::Polish||event->type()==QEvent::Show)
       &&!strcmp(receiver->metaObject()->className(),"LauncherWindow"))attachMenu((QWidget*)receiver,true);
    bool result=real?real(self,receiver,event):false;
    if(event->type()==QEvent::Show && receiver->isWidgetType()) {
        if(!strcmp(receiver->metaObject()->className(),"SettingWindow"))attachSettings(receiver);
        if(!strcmp(receiver->metaObject()->className(),"LauncherWindow"))attachMenu((QWidget*)receiver,true);
    }
    return result;
}
