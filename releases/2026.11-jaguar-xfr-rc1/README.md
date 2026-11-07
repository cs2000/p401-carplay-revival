# Jaguar XFR firmware RC1

Complete firmware, wireless CarPlay repair and Jaguar glass/clock/name features for compatible stock P401 units. No prior R1 or field-W3 development setup is needed. Read [compatibility](../../docs/compatibility.md) first; existing native factory settings are retained.

[**Download the firmware ZIP**](https://github.com/cs2000/p401-carplay-revival/raw/refs/heads/main/releases/2026.11-jaguar-xfr-rc1/P401_2026.11_JAGUAR_XFR_RC1.zip)

## Install

1. Extract the ZIP on your computer.
2. Copy these three files directly to the root of an empty **FAT32 USB drive under 16 GB**:

   ```text
   update
   zImage
   rootfs.img
   ```

3. With the vehicle parked and stable power available, insert the USB and restart the box.
4. Wait for the completion prompt without interrupting power or removing the USB, then remove the USB before normal startup.
5. Keep your MCU settings. If your saved link mode is USB-only, select **USB & Wireless CarPlay**, then pair your phone.

The Jaguar UI is included. Change its name under **Settings → CarPlay name → Change name → Save & restart**; re-pair the phone if needed. Do not mix other updater, factory-config or `msn_autocopy` files onto the firmware USB.

**This is a full firmware update. It does not back up your firmware. A failed flash can brick the unit; I offer no recovery image or method for an unbootable box. Use at your own risk.**

This exact complete image passed offline/native checks and awaits a vehicle installation test. The UI and W3 components have worked separately on my box.

[Checksums](SHA256SUMS.txt) · [Optional UI rollback / re-enable](../../recovery/2026.11-jaguar-xfr-rc1/README.md) · [Technical source and test records](../../experimental/ui1/full-image-rc1/README.md)
