# P401 CarPlay Revival

Newer menus and native wireless CarPlay fixes for Limcet/Arkmicro P401 interfaces. These fixes restored wireless CarPlay on my Jaguar XFR.

**Flash at your own risk. This does not back up your current firmware. A failed update can brick your unit, and I cannot provide a recovery image or method.**

## How to install this

Check [compatibility](docs/compatibility.md) first. Existing factory settings are retained; this is not a universal update for every CarPlay box.

1. [**Download the firmware ZIP**](https://github.com/cs2000/p401-carplay-revival/raw/refs/heads/main/releases/2026.11-w3-rc1/P401_2026.11_W3_RC1.zip) and extract it on your computer.
2. Use an empty **FAT32 USB drive under 16 GB**.
3. Copy these three files directly onto the USB—not inside another folder:

   ```text
   update
   zImage
   rootfs.img
   ```

4. With the vehicle parked and stable power available, insert the USB and restart the CarPlay box.
5. Wait for the update to finish. **Do not interrupt power or remove the USB while it is updating.** Follow the completion prompt, then remove the USB before the next normal startup.
6. If your saved setting is USB-only, select **USB & Wireless CarPlay** in Factory Settings, then pair your phone normally. Keep your existing MCU selection.

The filename is **`update`**, without an extension. It starts the full firmware update; an `msn_autocopy` folder is not needed.

## Test status

I've tested the fixes on my box. This combined download has passed offline checks but has not yet been tested in a vehicle, so it is labelled **rc1**.

[Release details and checksums](releases/2026.11-w3-rc1/README.md) · [Installation help](docs/installation.md) · [Technical notes](docs/README.md)

For Jaguar XFR owners starting from compatible stock P401 firmware or the full Jaguar RC1 release: [**complete Jaguar firmware RC2**](releases/2026.11-jaguar-xfr-rc2/README.md). It includes the wireless repair, glass/clock/name UI, connection status, appearance options and matching Settings, preserving existing factory settings. RC2 is offline/native checked and awaits a vehicle installation test. [Previous Jaguar RC1](releases/2026.11-jaguar-xfr-rc1/README.md) remains available.

The release folder contains only the installation guide, checksum file and firmware ZIP. Optional [full-image UI rollback controls](recovery/2026.11-jaguar-xfr-rc2/README.md) are separate. My older development installation has its own [small current-car update and exact previous-UI restore](upgrades/2026.11-jaguar-xfr-rc2/README.md); those files are only for its R1 + field-W3 launcher.

[UI1 source and lab notes](experimental/ui1/README.md) · [Cloud project handover](docs/cloud-handover.md)
