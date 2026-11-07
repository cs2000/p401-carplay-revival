# RC2 update for the existing development car

This small UI update is for my existing **R1 + field-W3 + Jaguar Glass/Clock installation**, whose previous installer was reported working on 7 November. It changes six UI/startup files and the GUI runner's W3 checksum row. It does not flash the kernel/rootfs or change the wireless repair, factory/MCU settings or saved name.

[**Download INSTALL.zip**](https://github.com/cs2000/p401-carplay-revival/raw/refs/heads/main/upgrades/2026.11-jaguar-xfr-rc2/INSTALL.zip)

**For stock units or the full Jaguar RC1 firmware, use the [full RC2 firmware](../../releases/2026.11-jaguar-xfr-rc2/README.md) instead.** Those installations use a different launcher; do not apply this overlay or its recovery files there.

## Apply to the current car

1. Extract `INSTALL.zip` on your computer.
2. Copy its **msn_autocopy** folder to the root of a FAT32 USB. On the prepared USB, replace only the active folder and retain the existing inactive rollback folder unchanged.
3. Insert the USB into the running box and wait for autocopy to finish.
4. Remove the USB, then fully power-cycle the box.

Open **Settings → Appearance → Personalise appearance** for accent colours, tile pictures and tile order. Exit and Settings remain fixed. **Settings → CarPlay name** retains the shared Bluetooth/Wi-Fi/CarPlay name with Save & restart. The CarPlay tile shows session status, and Advanced settings opens directly without its PIN prompt.

## Restore the previous working version

[**RESTORE_PREVIOUS_UI.zip**](RESTORE_PREVIOUS_UI.zip) is the exact previous successful Glass/Clock installer, unchanged. Apply its `msn_autocopy` folder in the same way to restore the previous UI, wrapper, compatibility checks, runner and W3 manifest together. Saved names/preferences and factory settings are retained.

[**DISABLE_UI.zip**](DISABLE_UI.zip) is the unchanged original rollback that returns to the native interface while retaining W3. It restores the old field runner/manifest and disables the UI.

Use only one active **msn_autocopy** folder. These recovery files require this field-W3 layout and a box that still boots and accepts autocopy. **They do not back up firmware or recover an unbootable unit.** Keep them separate from any full firmware USB.

RC2 passed fresh native ARM/offline checks; physical testing of this new version is pending. The previous successful car report applies to the restored old package, not RC2.

[Checksums](SHA256SUMS.txt) · [Source and validation records](../../experimental/ui1/full-image-rc2/README.md)
