# Installing the combined USB firmware

**This update does not back up your current firmware. Flashing can make the unit unusable. Neither the maintainer nor this project provides a recovery firmware, recovery route, or recovery method if it fails. Use it entirely at your own risk.**

## Before flashing

This is for the supported **firmware family and flash layout**, not any product with a similar menu. Read [compatibility](compatibility.md). The exact combined image is an offline-validated release candidate. Keeping settings does not prove that its kernel or drivers support every MCU/board.

The device must already have valid persistent settings in `/data/msncfg/MsnProductInfo.ini` and `/data/msncfg/FactoryConfig.ini`. The software's configuration lookup uses these files when present. The update does not invent missing values or import another unit's profile. A factory-settings export can help record your existing choices, but it is **not a firmware backup** and is not automatically imported by this package. If you cannot establish these prerequisites, do not treat this image as a universal update.

Avoid Factory Reset. Automatic userdata erasure has been removed; vendor factory-reset semantics are not supported by this build.

## Prepare the USB

1. Download the ZIP linked from the [release page](../releases/2026.11-w3-rc1/README.md).
2. Extract it on your computer. Check its SHA256 against the release checksums if possible.
3. Use an otherwise empty FAT32 USB drive below 16 GB, following the original supplier's update guide.
4. Copy these three files directly to the USB root:

```text
USB:/
  update
  zImage
  rootfs.img
```

Do not add `msn_factory_configs`, `msn_autocopy`, `UpConfig`, `userdata.img`, bootloader files, an old logger, or another firmware's files. The `update` file is deliberately just `kernel` and `filesystem`, each followed by CRLF. Do not edit it: the vendor updater uses substring matching, not a conventional commented configuration format.

Optional read-only verification from a checkout of this repository:

```text
python tools/verify_usb.py F:/
```

Substitute your USB drive letter. The verifier does not flash or modify anything.

## Flash

1. Park the vehicle and ensure stable power for the entire update.
2. Connect the prepared USB and restart/power on the interface through its normal update route. The existing bootloader detects the `update` file.
3. Once writing starts, do not interrupt power or unplug the USB. Wait for completion and follow the updater's removal/restart prompt.
4. Remove the update USB before another normal start so the update is not inadvertently repeated.
5. Check the display, touch, factory-system switching and direct USB CarPlay before using native wireless.

If the updater ignores the USB, do not add donor bootloaders or other image files to force it. If flashing or startup fails, the project has no recovery image or recovery method to offer.

## After flashing

Your existing MCU, touchscreen, Bluetooth/WLAN selections, volume, language and iPhone link mode are retained. Do not switch MCU type just because a manufacturer's name appears in the menu.

If you previously disabled native wireless, enable the vendor's **USB & Wireless CarPlay** option yourself in Factory Settings. The firmware deliberately does not change this saved preference. Use the box's normal pairing flow with the phone's Bluetooth and Wi-Fi enabled; accept the phone's CarPlay prompt. Disconnect any external wireless dongle and USB phone cable for a native-wireless test.

No diagnostic USB, autocopy update or second installation stage is required. No custom logger is included.
