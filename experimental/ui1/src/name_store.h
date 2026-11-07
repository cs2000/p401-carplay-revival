#ifndef P401_NAME_STORE_H
#define P401_NAME_STORE_H
#include <QtCore/qstring.h>
namespace Revival {
bool laboratory();
bool namesAvailable();
QString namesUnavailableReason();
bool validName(const QString &name);
QString savedName();
bool saveName(const QString &name, QString &error);
}
#endif
