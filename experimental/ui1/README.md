# Jaguar UI1 — experimental

**Development/source area, not a full firmware download.** Normal stock-to-Jaguar installation starts at the [complete firmware release](../../releases/2026.11-jaguar-xfr-rc1/README.md).

Starting from compatible stock P401 firmware: use the [complete Jaguar firmware RC1](../../releases/2026.11-jaguar-xfr-rc1/README.md). It includes the firmware, W3 repair and this exact UI library with a standalone launcher. The small overlay below remains for the older field installation; its prerequisite does not apply to the complete image.

The current development package is **Glass + Clock, 6 November 2026**. Fresh tests of its exact ARM binary cover the native Settings/save/restart-request flow, name reload, footer actions, clock and startup fallback. [Native evidence](candidates/glass-clock-2026-11-06/NATIVE_EVIDENCE.json) records the fixtures and limits.

The old public UI-only release folder was removed to avoid confusing it with the complete firmware. The exact historical [packaging snapshot](candidates/glass-clock-2026-11-06/MANIFEST.json) is retained for development. On 7 November I reported that its bugs were fixed on my P401 in my Jaguar XFR; [that report](../../docs/evidence/ui1-owner-report-2026-11-07.json) remains separate from the earlier PC checks and the new full-image candidate.

Six large photographic/glass tiles, permanent **Exit** and **Settings** footer buttons, turquoise accents and a centred Jaguar leaper/wordmark. A live clock replaces the Main label beside Home. Settings adds a custom CarPlay name and **Save & restart**; the saved name feeds Bluetooth, Wi-Fi and CarPlay's advertised SSID.

![Native ARM menu preview](candidates/glass-clock-2026-11-06/HOME.png)

**Status:** native ARM checks passed, followed by my successful device report for this exact installer. The existing W3 wireless CarPlay fix has also worked in the car. The clean public RC1 combined image remains a separate offline-checked artifact.

These packages target the existing **R1 + field W3 installation** used during development. They are not a universal update or an add-on for an arbitrary P401 installation. The public RC1 combined firmware uses a different startup layout; do not apply UI1 to it without adapting and checking that integration.

## Install on the matching development installation

1. Download [INSTALL.zip](candidates/glass-clock-2026-11-06/INSTALL.zip). Replace the USB's active **msn_autocopy** folder with the extracted folder. Keep an inactive **msn_autocopy_rollback** folder unchanged.
2. Insert it into the running box and wait for autocopy to complete.
3. Remove the USB, then fully power-cycle the box.
4. Open **Settings → CarPlay name** to change the name. Use 1–24 English letters, digits, spaces, hyphens or underscores. **Save & restart** applies it after reboot; forget the old phone pairing and pair again if necessary.

The name option is enabled for Bluetooth type 3 (SD-RDA). Existing MCU and factory settings are retained.

## Undo

Extract [ROLLBACK.zip](candidates/glass-clock-2026-11-06/ROLLBACK.zip) and use its **msn_autocopy** folder the same way. This archive is unchanged from the handover: it restores the exact prior GUI runner and W3 manifest, disables UI1 and retains the wireless fix. The saved custom name is ignored after rollback.

For a ready USB, an inactive rollback folder can be named **msn_autocopy_rollback**. The updater only recognises the exact name **msn_autocopy**. To switch, rename the active folder out of the way, then rename the rollback folder to **msn_autocopy**. Remove the USB after completion before the next normal startup.

**This does not back up the firmware. Install at your own risk. Rollback requires a box that still boots and accepts autocopy; I offer no recovery image or method for a bricked unit.**

[Build and lab notes](BUILDING.md) · [Current package hashes](candidates/glass-clock-2026-11-06/MANIFEST.json) · [Cloud handover](../../docs/cloud-handover.md)

The [original UI1 packages and historical evidence](packages/MANIFEST.json) remain unchanged. Their native screenshot is [here](evidence/XFR-menu.png).
