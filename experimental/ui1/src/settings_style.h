#ifndef P401_REVIVAL_SETTINGS_STYLE_H
#define P401_REVIVAL_SETTINGS_STYLE_H
class QWidget;
class QObject;
class QEvent;
namespace Revival {
// Only the native Settings/factory windows are eligible. These calls change
// widget presentation, never the native model, controls or configuration.
void applySettingsStyle(QWidget *window);
void settingsStyleEvent(QObject *receiver,QEvent *event);
}
#endif
