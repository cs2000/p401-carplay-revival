# Firmware 2026.11-w3-rc1

6 November 2026. Newer vendor menus, the matching kernel and the native wireless CarPlay fixes. Your existing factory settings and MCU selection are retained.

**Flash at your own risk. This does not back up your current firmware. A failed update can brick your unit, and I cannot provide a recovery image or method.**

[**Download the firmware ZIP**](https://github.com/cs2000/p401-carplay-revival/raw/refs/heads/main/releases/2026.11-w3-rc1/P401_2026.11_W3_RC1.zip)

## How to install this

1. Read [compatibility](../../docs/compatibility.md), then download and extract the ZIP.
2. Copy `update`, `zImage` and `rootfs.img` to the root of an empty **FAT32 USB drive under 16 GB**.
3. With stable power available, insert it and restart the CarPlay box.
4. Wait for completion without interrupting power or removing the USB. Follow the completion prompt and remove the USB before the next normal startup.
5. Enable **USB & Wireless CarPlay** if your saved mode is USB-only, then pair your phone. Keep the existing MCU setting.

`update` is the correct filename. No `msn_autocopy` folder is needed for this full firmware update.

I've tested these fixes on my box, but this combined download has only been checked offline. It remains a release candidate until the complete image has been tested in a vehicle.

[Installation help](../../docs/installation.md) · [Checksums](SHA256SUMS.txt) · [Technical manifest](manifest.json)
