#ifndef REVIVAL_CONNECTION_STATUS_H
#define REVIVAL_CONNECTION_STATUS_H

#include <QtCore/qstring.h>

namespace Revival {
// Read-only session status. The native signal is observed from process startup,
// including before the CarPlay window/plugin is created.
bool carPlayConnected();
unsigned carPlayStatusRevision();
QString carPlayStatusText();
}

#endif
