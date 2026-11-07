# Jaguar RC1 UI rollback

For the [complete Jaguar RC1 firmware](../../releases/2026.11-jaguar-xfr-rc1/README.md).

[**UI_ROLLBACK.zip — use the included native interface**](UI_ROLLBACK.zip) · [**ENABLE_JAGUAR_UI.zip — use the Jaguar interface**](ENABLE_JAGUAR_UI.zip)

Extract the chosen ZIP's **msn_autocopy** folder to the root of an otherwise clean FAT32 USB. Insert it into the running box and wait for autocopy, then remove the USB and power-cycle. Use one active autocopy folder at a time; keep these files separate from the full firmware update USB.

Each bundle writes only the UI enable/disable state. The wireless repair, factory/MCU settings and saved custom name remain intact.

**This requires a box that still boots and accepts autocopy. It does not restore previous firmware, back up the device or recover an unbootable unit.**

[Checksums](SHA256SUMS.txt)
