# Full Jaguar RC2 UI controls

For the [complete Jaguar RC2 firmware](../../releases/2026.11-jaguar-xfr-rc2/README.md). These state-only controls also work on the complete Jaguar RC1 firmware.

[**UI_ROLLBACK.zip — use the included native interface**](UI_ROLLBACK.zip) · [**ENABLE_JAGUAR_UI.zip — use the Jaguar interface**](ENABLE_JAGUAR_UI.zip)

Extract the chosen ZIP's **msn_autocopy** folder to the root of an otherwise clean FAT32 USB. Insert it into the running box and wait for autocopy, then remove the USB and power-cycle. Use one active autocopy folder at a time; keep these files separate from the full firmware update USB.

Each ZIP writes only the UI enable/disable state. The wireless repair, factory/MCU settings, saved name and appearance preferences are retained. These are the same exact state payloads used for the full RC1 release.

These are the standalone full-firmware controls. Never copy an old development field-W3 runner or manifest into the standalone firmware.

**These controls require a box that still boots and accepts autocopy. They do not restore previous firmware, back up the device or recover an unbootable unit.** To return to an older full firmware image, use that exact full firmware download; reflashing remains subject to the normal flash risk.

[Checksums](SHA256SUMS.txt)
