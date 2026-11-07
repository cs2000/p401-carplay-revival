#include "appearance_editor.h"
#include "preferences.h"
#include <QtGui/qapplication.h>
#include <QtGui/qdesktopwidget.h>
#include <QtGui/qwidget.h>
#include <QtGui/qboxlayout.h>
#include <QtGui/qpainter.h>
#include <QtGui/qpainterpath.h>
#include <QtGui/qpixmap.h>
#include <QtGui/qevent.h>
#include <QtCore/qvector.h>
#include <stdio.h>
#include "glass_artwork.h"

namespace Revival {
const QPixmap &tileArtwork() {
    // One shared decode for Home and the picture gallery. No extra resident
    // full-size pictures or animated effects are needed on the old ARM board.
    static QPixmap atlas;static bool loaded=false;
    if(!loaded) {
        loaded=true;
        if(atlas.loadFromData(p401_glass_tile_atlas,p401_glass_tile_atlas_size,"PNG")) {
            if(atlas.width()>768||atlas.height()>512)atlas=atlas.scaled(768,512,Qt::KeepAspectRatio,Qt::SmoothTransformation);
            fprintf(stderr,"REVIVAL: static glass artwork loaded %dx%d\n",atlas.width(),atlas.height());
        } else fprintf(stderr,"REVIVAL: glass artwork unavailable; using graphite tiles\n");
    }
    return atlas;
}
static const QColor background(14,17,18),surface(31,36,38),ink(240,241,238),muted(165,175,176);
static const char *appLabels[]={"CarPlay","Android Auto","Bluetooth","Music","Video","Mirroring"};
static const char *photoLabels[]={"Mountain road","Coast","Flow","Audio","Camera","Glass"};
static QString word(const char *s){return QString::fromUtf8(s);}
static void label(QPainter &p,const QRect &r,const QString &s,int size,QColor c,int alignment=Qt::AlignCenter,bool bold=false) {
    QFont f("WenQuanYi Micro Hei");f.setPixelSize(size);f.setBold(bold);p.setFont(f);p.setPen(c);p.drawText(r,alignment,s);
}
struct AppearanceHit {QRect rect;int action,value;AppearanceHit():action(-1),value(0){} AppearanceHit(QRect r,int a,int v):rect(r),action(a),value(v){} };
enum {TabAction,AccentAction,AppAction,PictureAction,OrderAction,MoveAction,CancelAction,DefaultAction,SaveAction};
static void glass(QPainter &p,QRect r,QColor border,bool down=false) {
    QRectF area=r.adjusted(1,1,-1,-1);QPainterPath path;path.addRoundedRect(area,8,8);
    QLinearGradient g(area.topLeft(),area.bottomLeft());g.setColorAt(0,down?QColor(52,67,70):QColor(47,54,58));g.setColorAt(1,surface);
    p.fillPath(path,g);p.setPen(QPen(border,1));p.setBrush(Qt::NoBrush);p.drawPath(path);
    p.setPen(QColor(255,255,255,35));p.drawLine(r.x()+10,r.y()+2,r.right()-10,r.y()+2);
}
static void photo(QPainter &p,QRect r,int index) {
    QRectF area=r.adjusted(2,2,-2,-2);QPainterPath path;path.addRoundedRect(area,7,7);p.save();p.setClipPath(path);
    p.fillRect(r,surface);const QPixmap &atlas=tileArtwork();
    if(!atlas.isNull()) {
        qreal w=qreal(atlas.width())/3,h=qreal(atlas.height())/2;
        QRectF source((index%3)*w,(index/3)*h,w,h);qreal ratio=area.width()/area.height();
        if(source.width()/source.height()>ratio){qreal crop=source.height()*ratio;source.setX(source.x()+(source.width()-crop)/2);source.setWidth(crop);}
        else {qreal crop=source.width()/ratio;source.setY(source.y()+(source.height()-crop)/2);source.setHeight(crop);}
        p.setRenderHint(QPainter::SmoothPixmapTransform);p.drawPixmap(area,atlas,source);
    }
    QLinearGradient shade(area.topLeft(),area.bottomLeft());shade.setColorAt(0,QColor(4,8,11,0));shade.setColorAt(1,QColor(4,8,11,215));p.fillPath(path,shade);p.restore();
}

class AppearanceEditor:public QWidget {
    AppearancePreferences draft;QVector<AppearanceHit> hits;int tab,selectedKind,pressed;QString error;
    QColor accent()const{return appearanceAccent(draft.accent);}
    void button(QPainter &p,QRect r,const QString &s,int action,int value=0,bool selected=false,bool enabled=true,int font=21) {
        bool down=pressed==hits.size();QColor border=selected?accent():QColor(72,79,80);
        glass(p,r,border,down);if(selected){QColor glow=accent();glow.setAlpha(25);p.fillRect(r.adjusted(3,3,-3,-3),glow);}
        label(p,r,s,font,enabled?ink:QColor(95,104,107));hits.append(AppearanceHit(r,enabled?action:-1,value));
    }
    int orderIndex()const{for(int i=0;i<6;++i)if(draft.order[i]==selectedKind)return i;return 0;}
public:
    AppearanceEditor():QWidget(0,Qt::FramelessWindowHint|Qt::WindowStaysOnTopHint),draft(appearancePreferences()),tab(0),selectedKind(0),pressed(-1) {
        setAttribute(Qt::WA_DeleteOnClose);setAttribute(Qt::WA_OpaquePaintEvent);setObjectName("RevivalAppearanceEditor");setGeometry(QApplication::desktop()->screenGeometry());
    }
protected:
    void paintEvent(QPaintEvent *) {
        QPainter p(this);p.fillRect(rect(),background);p.scale(qreal(width())/800,qreal(height())/480);p.setRenderHint(QPainter::Antialiasing);hits.clear();
        label(p,QRect(24,8,752,42),word("Appearance"),27,ink,Qt::AlignLeft|Qt::AlignVCenter);
        label(p,QRect(24,46,752,22),word("Make it yours. Save to apply without restarting."),16,muted,Qt::AlignLeft|Qt::AlignVCenter);
        button(p,QRect(24,78,240,49),word("Accent colour"),TabAction,0,tab==0);
        button(p,QRect(280,78,240,49),word("Tile pictures"),TabAction,1,tab==1);
        button(p,QRect(536,78,240,49),word("Tile order"),TabAction,2,tab==2);
        if(tab==0) {
            for(int i=0;i<6;++i) {
                QRect r(24+(i%3)*256,147+(i/3)*113,240,97);bool selected=draft.accent==i;
                glass(p,r,selected?accent():QColor(72,79,80),pressed==hits.size());
                p.setPen(Qt::NoPen);p.setBrush(appearanceAccent(i));p.drawEllipse(QRectF(r.x()+22,r.y()+23,40,40));
                label(p,QRect(r.x()+75,r.y()+8,157,78),appearanceAccentName(i),20,ink,Qt::AlignLeft|Qt::AlignVCenter);
                if(selected){p.setPen(QPen(QColor(16,27,29),3));p.drawLine(r.x()+32,r.y()+43,r.x()+39,r.y()+50);p.drawLine(r.x()+39,r.y()+50,r.x()+53,r.y()+34);}
                hits.append(AppearanceHit(r,AccentAction,i));
            }
        } else if(tab==1) {
            for(int i=0;i<6;++i)button(p,QRect(24,143+i*40,246,36),word(appLabels[i]),AppAction,i,selectedKind==i,true,19);
            label(p,QRect(294,140,482,29),word("Picture for ")+word(appLabels[selectedKind]),21,ink,Qt::AlignLeft|Qt::AlignVCenter);
            for(int i=0;i<6;++i) {
                QRect r(294+(i%3)*163,179+(i/3)*104,156,94);photo(p,r,i);
                p.setBrush(Qt::NoBrush);p.setPen(QPen(draft.pictures[selectedKind]==i?accent():QColor(80,91,95),draft.pictures[selectedKind]==i?3:1));p.drawRoundedRect(r.adjusted(2,2,-2,-2),7,7);
                label(p,QRect(r.x()+4,r.bottom()-31,r.width()-8,26),word(photoLabels[i]),16,ink);
                hits.append(AppearanceHit(r,PictureAction,i));
            }
        } else {
            int selected=orderIndex();
            for(int i=0;i<6;++i)button(p,QRect(24,143+i*40,438,36),QString::number(i+1)+"    "+word(appLabels[draft.order[i]]),OrderAction,draft.order[i],selectedKind==draft.order[i],true,20);
            label(p,QRect(490,145,286,42),word(appLabels[selectedKind]),23,ink);
            button(p,QRect(498,201,270,65),word("Move up"),MoveAction,-1,false,selected>0);
            button(p,QRect(498,280,270,65),word("Move down"),MoveAction,1,false,selected<5);
            label(p,QRect(486,352,294,42),word("Exit and Settings stay in the footer."),17,muted,Qt::AlignCenter|Qt::TextWordWrap);
        }
        if(!error.isEmpty())label(p,QRect(24,389,752,24),error,16,QColor(230,153,126));
        button(p,QRect(24,418,164,49),word("Cancel"),CancelAction);
        button(p,QRect(204,418,240,49),word("Restore defaults"),DefaultAction);
        button(p,QRect(550,418,226,49),word("Save appearance"),SaveAction,0,true);
    }
    int hitAt(QPoint position)const {
        QPoint p(position.x()*800/qMax(width(),1),position.y()*480/qMax(height(),1));
        for(int i=0;i<hits.size();++i)if(hits[i].rect.contains(p))return i;return -1;
    }
    void mousePressEvent(QMouseEvent *e){pressed=hitAt(e->pos());update();}
    void mouseReleaseEvent(QMouseEvent *e) {
        int h=hitAt(e->pos());if(h<0||h!=pressed){pressed=-1;update();return;}
        AppearanceHit hit=hits.at(h);pressed=-1;error.clear();
        switch(hit.action) {
        case TabAction:tab=hit.value;break;
        case AccentAction:draft.accent=hit.value;break;
        case AppAction:case OrderAction:selectedKind=hit.value;break;
        case PictureAction:draft.pictures[selectedKind]=hit.value;break;
        case MoveAction:{int from=orderIndex(),to=from+hit.value;if(to>=0&&to<6){int other=draft.order[to];draft.order[to]=selectedKind;draft.order[from]=other;}break;}
        case CancelAction:close();return;
        case DefaultAction:draft=defaultAppearancePreferences();selectedKind=0;break;
        case SaveAction:if(saveAppearancePreferences(draft,error)){close();return;}break;
        }
        update();
    }
};

class AppearancePanel:public QWidget {
public:AppearancePanel(){setObjectName("RevivalAppearancePanel");}
protected:
    void paintEvent(QPaintEvent *) {
        QPainter p(this);p.fillRect(rect(),background);p.setRenderHint(QPainter::Antialiasing);
        label(p,QRect(20,22,width()-40,50),word("Your Jaguar, your style"),25,ink);
        label(p,QRect(20,83,width()-40,54),word("Accent colours, tile pictures and tile order"),20,muted,Qt::AlignCenter|Qt::TextWordWrap);
        for(int i=0;i<6;++i){int x=width()/2-122+i*45;p.setPen(Qt::NoPen);p.setBrush(appearanceAccent(i));p.drawEllipse(QRectF(x,145,20,20));}
        QRect button(30,195,width()-60,65);glass(p,button,accentColor());label(p,button,word("Personalise appearance"),23,ink);
        label(p,QRect(20,278,width()-40,80),word("Changes apply straight away. Exit and Settings always stay in the footer."),18,muted,Qt::AlignCenter|Qt::TextWordWrap);
    }
    void mouseReleaseEvent(QMouseEvent *e) {
        if(QRect(30,195,width()-60,65).contains(e->pos())){AppearanceEditor *editor=new AppearanceEditor;editor->show();editor->raise();}
    }
};
QLayout *appearanceSettingsLayout(){QVBoxLayout *layout=new QVBoxLayout;layout->setContentsMargins(0,0,0,0);layout->addWidget(new AppearancePanel);return layout;}
}
