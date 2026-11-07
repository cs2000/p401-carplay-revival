# UI1 Glass + Clock — development overlay

For the existing **R1 + field W3** installation used in this project. The public RC1 combined image has a different startup layout; this is not an add-on for that clean layout or unrelated units.

The package contains the approved glass/photo theme, a live clock instead of Main, six large tiles, door-and-arrow Exit and Settings footer buttons, the CarPlay-name setting, and an earlier launcher cover to prevent the stock menu appearing while the theme starts. Factory/MCU settings and the working W3 components are retained.

## Install

1. Extract **INSTALL.zip**. Replace the USB's active **msn_autocopy** folder with the extracted folder. Keep **msn_autocopy_rollback** inactive and unchanged; do not merge the two.
2. Insert the USB into the running box and wait for autocopy to complete.
3. Remove the USB, then fully power-cycle the box.
4. To rename it, open **Settings → CarPlay name → Change name**. Enter 1–24 ASCII letters, digits, spaces, hyphens or underscores, then **Continue → Save & restart**. Forget the old phone pairing and pair again if necessary.

Naming remains restricted to the verified SD-RDA Bluetooth type 3. Other configurations show an explanation rather than hiding the setting.

## Undo

**ROLLBACK.zip** is byte-for-byte identical to the preserved handover rollback. Use its **msn_autocopy** folder the same way. It restores the prior GUI runner/W3 manifest, disables UI1 and retains the wireless fix. The saved name is ignored after rollback. An existing inactive **msn_autocopy_rollback** folder containing that payload can still be used by renaming it to **msn_autocopy** after moving the active folder out of the way.

## Evidence and limits

The exact new ARM library passed fresh native GUI checks: 13 naming cases, 11 menu/startup cases and live-clock/header restoration. The real editor saved a private file and reached the native reboot request; fresh processes applied the name to Bluetooth desired name, hostapd and CarPlay advertisement. These are isolated PC checks with synthetic profiles and a fake framebuffer. Physical radio renaming, physical reboot and cold-boot timing remain unconfirmed.

`NATIVE_EVIDENCE.json`, `DELIVERY_CHECKS.json` and `MANIFEST.json` record exact hashes and test scope. `HOME.png` shows the actual ARM renderer with a synthetic English app model. `SOURCE.zip` contains source, build notes and test tools; original packages and public RC1 remain unchanged. No release has been published.

**This does not back up the firmware. Install at your own risk. Rollback requires a box that still boots and accepts autocopy; I offer no recovery image or method for a bricked unit.**
