# How to install this

**Flash at your own risk. This does not back up your current firmware. A failed update can brick your unit, and I cannot provide a recovery image or method.**

Check [compatibility](compatibility.md) before starting. This combined release is awaiting a vehicle test.

For the Jaguar interface, use the [full Jaguar RC2 bundle](../releases/2026.11-jaguar-xfr-rc2/README.md), including when upgrading the complete Jaguar RC1 release. It uses the same three-file USB procedure below. The [small RC2 update](../upgrades/2026.11-jaguar-xfr-rc2/README.md) is only for my older field-W3 development installation and uses its separate autocopy instructions.

1. [Download the firmware ZIP](../releases/2026.11-w3-rc1/README.md) and extract it on your computer.
2. Use an empty **FAT32 USB drive under 16 GB**.
3. Copy the three extracted files directly to the USB root:

   ```text
   USB:/
     update
     zImage
     rootfs.img
   ```

4. With the vehicle parked and stable power available, insert the USB and restart the CarPlay box.
5. Wait for the update to finish. **Do not interrupt power or unplug the USB during the update.** Follow the completion prompt and remove the USB before the next normal startup.
6. Check the display, touch and switching back to the car's original interface. For native wireless, select **USB & Wireless CarPlay** if necessary and pair your phone with Bluetooth and Wi-Fi enabled. Disconnect any phone cable or external wireless adapter for this test.

## Do I need another update folder?

No. The **`update`** file—spelled with a leading **u**, with no extension—tells the bootloader to install the other two files. `msn_autocopy` is a separate mechanism for copying individual files into an installed system; this package is a full firmware update.

Use only the three files from this ZIP. Do not mix them with old update files or factory-settings exports. If the update does not start, do not add bootloader files to force it.

## Settings

Keep your existing MCU and hardware selections. The update retains saved settings, including a USB-only CarPlay preference. Avoid Factory Reset; it is not supported by this build.

The unit needs its existing factory configuration saved in userdata. Missing settings stop startup instead of loading another unit's defaults. See [compatibility](compatibility.md) for the required files. A settings export is **not a firmware backup**.

[Checksums](../releases/2026.11-w3-rc1/SHA256SUMS.txt) and an optional [USB verification tool](../tools/verify_usb.py) are available for checking the download.
