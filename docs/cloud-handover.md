# Cloud continuation — 6 November 2026

The next task continues the existing P401 project. The working wireless repair is W3. The current development work is the Jaguar UI1 extension and editable CarPlay network name. Start with `python tools/check_cloud_handover.py` and [UI1](../experimental/ui1/README.md).

## State at handover

| Item | Status |
| --- | --- |
| R1 firmware / November 2025 vendor kernel and menus | Installed and boots on my P401 |
| Native wireless CarPlay with W3 | Worked on the real box; I confirmed success after earlier repeated failures |
| Public combined firmware `2026.11-w3-rc1` | Offline checks passed; the combined ZIP itself has not been vehicle-tested |
| Jaguar UI1 menu and custom name | Actual ARM GUI and delivery checks passed on PC; physical radio renaming/reboot not yet tested |
| Prepared UI1 USB | Active `msn_autocopy` plus inactive `msn_autocopy_rollback`; last local check matched the prepared payloads |
| Full flash backup / recovery | No verified complete restore route; no full-backup button was implemented |

The USB and physical device remain local. A Cloud task cannot inspect or flash them directly. Existing local captures and the old WSL lab remain on the original PC; the public repo contains redacted findings, exact current packages, source and test evidence.

## Device and compatibility

The development box is a Limcet/Arkmicro P401 in a Jaguar XFR, with an 800×480 resistive display. Its working configuration uses MCU type 7 / CheKuShiDai, Bluetooth type 3 / SD-RDA5876 and WLAN type 1 / RTL8189FS. Selecting the Limcet MCU profile broke touch; changing it back through autocopy recovered it. **Do not force my MCU or factory profile onto other units.**

The R1 adaptation uses vendor V3.22.1 components from the P306-labelled donor dated 21 November 2025. P301/P305/P306/P401/P701 are product or build-family labels, not a reliable chronological ranking. The kernel is the vendor Linux 3.4.0 #396 binary; it was not rewritten from scratch. MCU support alone does not establish kernel, board, display, flash, radio or ABI compatibility.

The real native CarPlay application on this box is `/usr/bin/carplay`. `sink` is the Android Auto component here. A different project's `carplay-sidecar` architecture must not be assumed to describe this firmware.

## What fixed wireless CarPlay

Wired USB CarPlay continued to work while native wireless paired over Bluetooth and automatically joined Wi-Fi but stalled at connecting. Repeated physical logging trips were costly. The successful W3 change retained the licensed vendor stack and fixed two network behaviours:

* A two-byte `libAirPlay.so` patch at file offset `0x244b4`, ARM bytes `411fa013` → `0410a013`, removes the exclusion of IPv6 link-local addresses. Patched SHA256: `551112f2b5e525a0ff4994357ee1563c5d1e1dad56f59df6724962a0be8e34db`.
* BusyBox 1.38.0 `udhcpd` provides correct unicast OFFER/ACK behaviour for the observed iPhone flags=0 case. Binary SHA256: `bddafb863e3f37da68fc680db389f0c1b4c5fd0468953580f0f4422726c382d7`.

Prior W2 hostapd interworking settings were retained. On the development installation the overrides are scoped to the CarPlay process under `/data/p401-w3`; MFi/license authentication material was not modified. The public RC1 integrates the same fixes into a clean release layout. See [technical notes](README.md) for the detailed evidence and release provenance.

I reported that the problem began with iOS 17 after working on iOS 16. That timing is an observation, not proof of a documented Apple protocol change. Do not claim an Apple release note or authentication expiry explains it without evidence.

## Accepted UI design

Use the XFR layout with the Classic Jaguar turquoise lighting: six large tiles in a 3×2 grid, with permanent Exit and Settings footer buttons. No horizontal launcher scrolling is required. Main tiles are CarPlay, Android Auto, Bluetooth, Music, Video and Mirroring.

Use the supplied stacked Jaguar leaper above the classic JAGUAR wordmark and underline, centred over the middle column at screen x=400. The final choice has **no XF text and no R badge**. Exit replaces the AV In label and uses a door-and-arrow icon, while forwarding to the original native AV In action (application ID 9). Do not restore a car icon or reintroduce abandoned badge designs.

`experimental/ui1/evidence/XFR-menu.png` is the final native ARM screenshot, not a browser mock-up. The source uses Qt painting and the matching vendor Qt 4.7.4 ABI; it does not replace the vendor application implementations.

## Custom name implementation

Settings → CarPlay name provides a keyboard, validation, save confirmation and **Save & restart**. Names are 1–24 ASCII letters, digits, spaces, hyphens or underscores. The saved file is `/data/carplay-revival/network-name`, written atomically with fsync/rename and private file permissions. Invalid/missing files fall back to vendor naming.

The name is cached once per application startup and changes the native Bluetooth desired name, hostapd SSID and CarPlay-advertised SSID together after reboot. The feature is enabled only for tested Bluetooth type 3; it does not assume an MCU type. Native restart uses `SettingWindow::onReboot` and checks the native reboot lock. Re-pairing the phone may be necessary.

Important hook boundaries:

* The Bluetooth hook only changes the verified `BtSettingPanel::onRecvDeviceName` call site: function start `0x2b4c8`, return offset `+0x2a0`; instruction guards at `+0x298` and `+0x29c`.
* `MsnIniConfig::setValue` changes only `ssid` in the two hostapd config paths.
* `MsnApplication::setTag` changes only the CarPlay SSID tag `0x11017`.
* Unrelated configuration is untouched; child processes do not inherit UI `LD_PRELOAD`.
* The launcher forwards the vendor model's role-35 application IDs: Music 2, CarPlay 4, Android Auto 13, Mirroring 11, Bluetooth 3, Video 7, Exit 9, Settings 8.

## Startup and rollback contract

UI1 is currently tied to the **development R1 + field W3 startup layout**, not the public RC1 clean layout. The W3 manifest pins the GUI runner. UI1 changes that runner and updates only its row in the W3 manifest; failing to do both deactivates W3. The UI wrapper and all ABI-sensitive vendor files are CRC/length checked before loading.

The extension checks readiness and disables itself after a crash or a 60-second startup timeout, then attempts to start the stock interface. UI failure must not become a prerequisite for the underlying wireless repair. Exact prior runner and manifest files are retained in `experimental/ui1/baseline` and the rollback ZIP.

The installer has six files; rollback has three. Neither writes a kernel, rootfs, MCU profile or other factory settings. The current installer SHA256 is `2d43baa7ce7f244e48fcb14cde7d9a853be6e599f3b3fa47d8ab83391b06c53f`; the contained UI library is `aac2e11c9255b82c6fc76e7e824585773019e762d2c9dfaef52cbd7299c3ac35`. The rollback archive was normalized during migration to contain an active `msn_autocopy` root; its payload bytes match the tested rollback. Its current hash is in the package manifest.

I explicitly agreed to continue device feature work using the saved files as fallback. This does not establish brick recovery. Retain the warning that installation does not back up existing firmware and no recovery image or method is offered for an unbootable unit.

## Next Cloud work

First verify the handover and report readiness. Do not silently change device code or rebuild/relabel a tested package merely because the task moved to Cloud. No UI1 vehicle test result had been supplied at handover.

For later development, see [build and lab notes](../experimental/ui1/BUILDING.md). Device C++ and exact packages are available here. Native simulation still needs its Linux environment recreated and the preserved WSL launcher paths ported. The original four native cases and 52 delivery checks are historical evidence for the packaged hash, not a new Cloud run.

Keep public installation instructions short, use first-person wording for my experience, and keep technical detail in linked documents. Do not add a public feature claim about the absence of a logger. Do not require repeated car trips for weak candidates: exhaust relevant offline checks and state what physical testing alone can establish. Keep personal captures, phone identifiers and raw field logs out of GitHub.
