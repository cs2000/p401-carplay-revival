#ifndef P401_PREFERENCES_H
#define P401_PREFERENCES_H
#include <QtCore/qstring.h>
#include <QtGui/qcolor.h>

namespace Revival {
// The six known launcher kinds retain their native actions. Order is a
// permutation of those kinds; pictures are indices into the six-photo atlas.
struct AppearancePreferences {
    int accent;
    int order[6];
    int pictures[6];
};
AppearancePreferences defaultAppearancePreferences();
AppearancePreferences appearancePreferences();
bool validAppearancePreferences(const AppearancePreferences &value);
bool saveAppearancePreferences(const AppearancePreferences &value, QString &error);
QColor appearanceAccent(int index);
QString appearanceAccentName(int index);
QColor accentColor();
int tileOrderRank(int kind);
int tilePictureIndex(int kind);
unsigned preferencesRevision();
}
#endif
