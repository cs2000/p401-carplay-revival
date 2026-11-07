# Jaguar XFR firmware RC2

Complete firmware, W3 wireless CarPlay repair and the Jaguar glass interface for [compatible P401 hardware](../../docs/compatibility.md). Install from matching stock firmware or upgrade the full Jaguar RC1 release with this same bundle. No R1 or field-W3 development setup is needed.

[**Download the full firmware ZIP**](https://github.com/cs2000/p401-carplay-revival/raw/refs/heads/main/releases/2026.11-jaguar-xfr-rc2/P401_2026.11_JAGUAR_XFR_RC2.zip)

RC2 adds CarPlay **Waiting for phone / Connected**, six accent colours, selectable tile pictures/order, matching graphite Settings and direct access to Advanced settings without its PIN prompt. Exit and Settings stay fixed in the Home footer. Custom Bluetooth/Wi-Fi/CarPlay naming and the clock remain included.

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

Existing factory/MCU settings, saved custom name and appearance preferences are retained. If you previously disabled the Jaguar UI, use the separate [re-enable bundle](../../recovery/2026.11-jaguar-xfr-rc2/README.md). Avoid Factory Reset; it is not supported by this build.

Use **Settings → Appearance → Personalise appearance** for colours, pictures and tile order. Use **Settings → CarPlay name → Change name → Save & restart** for the shared radio/CarPlay name; re-pair the phone if needed.

Do not mix other updater, factory-config or `msn_autocopy` files onto the firmware USB. A full Jaguar RC1 installation uses this same full bundle.

**This is a full firmware update. It does not back up your firmware. A failed flash can brick the unit; I offer no recovery image or method for an unbootable box. Use at your own risk.**

RC2 is native/offline checked and awaits testing in a vehicle. My successful earlier UI/W3 reports do not establish physical success for this new binary or complete firmware image.

[Checksums](SHA256SUMS.txt) · [UI rollback / re-enable](../../recovery/2026.11-jaguar-xfr-rc2/README.md) · [Technical source and test records](../../experimental/ui1/full-image-rc2/README.md)
